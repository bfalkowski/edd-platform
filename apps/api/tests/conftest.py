import os


os.environ["EDD_PLATFORM_STORAGE_BACKEND"] = "memory"
# Set before edd_platform_api.main is imported: its load_env_files() would
# otherwise walk up from a worktree and load the main checkout's .env.local
# with override=True, putting real provider keys in the test process.
os.environ["EDD_PLATFORM_E2E"] = "1"
