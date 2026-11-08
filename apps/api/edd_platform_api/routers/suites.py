from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_agent_version_or_404,
    get_project_or_404,
)
from edd_platform_api.routers import runs as _runs_router
from edd_platform_api.schemas import (
    AgentVersion,
    EvalContract,
    EvalResult,
    RunCreate,
    RunEvaluateCreate,
    Scenario,
    SuiteResult,
    SuiteRunCreate,
    SuiteTestResult,
)
from edd_platform_api.state import _eval_contracts, _eval_results, _runs, _scenarios

router = APIRouter()


def active_tests(project_id: str, agent_design_id: str) -> List[Tuple[Scenario, EvalContract]]:
    """An agent's tests: each active scenario with its newest eval contract, oldest first.

    Matches the console's saved-test list (`pairActiveTests` in apps/web/src/api.ts).
    """
    scenarios = sorted(
        (
            scenario
            for scenario in _scenarios.values()
            if scenario.project_id == project_id
            and scenario.agent_design_id == agent_design_id
            and scenario.status == "active"
        ),
        key=lambda scenario: scenario.created_at,
    )
    tests = []
    for scenario in scenarios:
        contracts = [
            contract
            for contract in _eval_contracts.values()
            if contract.project_id == project_id and contract.scenario_id == scenario.id
        ]
        if contracts:
            tests.append((scenario, max(contracts, key=lambda contract: contract.updated_at)))
    return tests


def latest_eval_for_test(
    *,
    project_id: str,
    version_id: str,
    scenario_id: str,
    eval_contract_id: str,
) -> Optional[EvalResult]:
    matches = []
    for eval_result in _eval_results.values():
        run = _runs.get(eval_result.run_id)
        if (
            eval_result.project_id == project_id
            and eval_result.eval_contract_id == eval_contract_id
            and run is not None
            and run.agent_version_id == version_id
            and run.scenario_id == scenario_id
        ):
            matches.append(eval_result)
    return max(matches, key=lambda eval_result: eval_result.created_at, default=None)


def suite_result_for_version(project_id: str, version: AgentVersion) -> SuiteResult:
    tests = [
        SuiteTestResult(
            scenario_id=scenario.id,
            eval_contract_id=contract.id,
            eval_result=latest_eval_for_test(
                project_id=project_id,
                version_id=version.id,
                scenario_id=scenario.id,
                eval_contract_id=contract.id,
            ),
        )
        for scenario, contract in active_tests(project_id, version.agent_design_id)
    ]
    return SuiteResult(
        agent_design_id=version.agent_design_id,
        agent_version_id=version.id,
        passed=sum(1 for test in tests if test.eval_result is not None and test.eval_result.passed),
        total=len(tests),
        tests=tests,
    )


def get_agent_version_for_agent_or_404(
    project_id: str, agent_id: str, version_id: str
) -> AgentVersion:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    version = get_agent_version_or_404(project_id, version_id)
    if version.agent_design_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent version not found")
    return version


@router.post(
    "/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}/suite-runs",
    status_code=201,
)
def run_version_suite(
    project_id: str,
    agent_id: str,
    version_id: str,
    payload: SuiteRunCreate,
) -> SuiteResult:
    version = get_agent_version_for_agent_or_404(project_id, agent_id, version_id)
    tests = active_tests(project_id, agent_id)
    if not tests:
        raise HTTPException(status_code=400, detail="Agent has no active tests to run.")
    # One test at a time; parallel or queued execution is out of scope.
    for scenario, contract in tests:
        run = _runs_router.create_run(
            project_id,
            RunCreate(
                agent_design_id=agent_id,
                agent_version_id=version.id,
                scenario_id=scenario.id,
                eval_contract_id=contract.id,
                mode=payload.mode,
                provider=payload.provider,
                model=payload.model,
            ),
        )
        _runs_router.evaluate_run(
            project_id,
            run.id,
            RunEvaluateCreate(eval_contract_id=contract.id, judge_mode=payload.judge_mode),
        )
    return suite_result_for_version(project_id, version)


@router.get(
    "/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}/suite-result"
)
def get_version_suite_result(project_id: str, agent_id: str, version_id: str) -> SuiteResult:
    version = get_agent_version_for_agent_or_404(project_id, agent_id, version_id)
    return suite_result_for_version(project_id, version)
