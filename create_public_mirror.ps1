# Create Public Mirror Script (Robust Version)
$source = "c:\GitHub\CalibreWEB\repo"
$dest = "c:\GitHub\CalibreWEB\public_mirror"

# 1. Clean Destination (Nuke)
if (Test-Path $dest) {
    Write-Host "Wiping old mirror..."
    Remove-Item -Path $dest -Recurse -Force
}
New-Item -Path $dest -ItemType Directory | Out-Null

# 2. Define Safe Files/Folders to Copy
# Explicitly listing guides to avoid wildcard issues
$filesToCopy = @(
    "cps",
    "test",
    "CONTRIBUTING.md",
    "DOCUMENTATION.md",
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "README_DEPLOYMENT.md",
    "ROADMAP.md",
    "SECURITY.md",
    "admin_full_access_guide.md",
    "secondary_user_guide.md",
    "user_registration_guide.md",
    "install_binaries.sh",
    "requirements.txt",
    "optional-requirements.txt",
    "pyproject.toml",
    "setup_deployment.sh",
    "update_from_git.sh",
    "update_users.py",
    "cron_cleanup.py",
    "enable_new_sidebar_sections.py",
    "hierarchy_endpoints.py",
    "cps.py",
    ".gitignore",
    ".github"
)

# 3. Copy Loop
foreach ($item in $filesToCopy) {
    $srcPath = Join-Path $source $item
    $destPath = Join-Path $dest $item
    
    if (Test-Path $srcPath) {
        if (Test-Path $srcPath -PathType Container) {
            Copy-Item -Path $srcPath -Destination $dest -Recurse -Force
        }
        else {
            Copy-Item -Path $srcPath -Destination $dest -Force
        }
        Write-Host "Copied: $item"
    }
    else {
        Write-Warning "Missing source file: $item"
    }
}

# 4. Remove artifacts from destination (Safety Check)
$unsafe = @(
    "$dest\cps\__pycache__",
    "$dest\test\__pycache__"
)
foreach ($u in $unsafe) {
    if (Test-Path $u) { Remove-Item -Path $u -Recurse -Force }
}

# 5. Initialize New Git (Fresh Start)
Set-Location $dest
git init
git add .
git commit -m "Public Release: Content Update"

Write-Host "Public Mirror Regenerated at $dest"
