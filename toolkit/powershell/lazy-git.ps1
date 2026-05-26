Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Check if inside a git repo
git rev-parse --is-inside-work-tree 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not inside a git repository."
    exit 1
}

# Get current branch
$branch = (git symbolic-ref --quiet --short HEAD 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($branch)) {
    Write-Error "Detached HEAD is not supported."
    exit 1
}

# Check upstream
git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "No upstream configured for $branch."
    exit 1
}

# Check committer identity
$committerIdent = git var GIT_COMMITTER_IDENT 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($committerIdent)) {
    Write-Error "Git committer identity is not configured."
    exit 1
}

# Build commit message
$now            = Get-Date
$month          = $now.ToString("MMMM")
$day            = $now.Day
$year           = $now.Year
$time           = $now.ToString("h:mm tt")
$tzOffset       = [System.TimeZoneInfo]::Local.GetUtcOffset($now)
$tzFormatted    = "UTC{0}{1:hh\:mm}" -f $(if ($tzOffset -ge [TimeSpan]::Zero) { "+" } else { "" }), $tzOffset

$suffix = switch ($day) {
    { $_ -in 11, 12, 13 } { "th"; break }
    { $_ % 10 -eq 1 }     { "st"; break }
    { $_ % 10 -eq 2 }     { "nd"; break }
    { $_ % 10 -eq 3 }     { "rd"; break }
    default                { "th" }
}

$committerName   = ($committerIdent -split ' <')[0]
$committerOffset = ($committerIdent.Trim() -split '\s+')[-1]
$ts              = [int][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$commitMessage   = "upd: lazily commit on $month $day$suffix, $year $time $tzFormatted $committerOffset by $committerName"
$stashName       = "lazy-git-autostash-$ts"
$tempBranch      = "lazy-git-temp-$ts"
$stashed         = $false
$tempBranchCreated = $false
$currentBranch   = $branch

function Resolve-RemainingConflicts {
    $conflictPaths = git diff --name-only --diff-filter=U 2>$null
    if ([string]::IsNullOrWhiteSpace($conflictPaths)) { return }
    foreach ($p in ($conflictPaths -split "`n" | Where-Object { $_ -ne '' })) {
        git checkout --theirs -- $p 2>$null
        if ($LASTEXITCODE -eq 0) {
            git add -- $p
        } else {
            git rm -f -- $p 2>$null | Out-Null
        }
    }
}

function Invoke-Cleanup {
    git rebase --abort     2>$null | Out-Null
    git merge --abort      2>$null | Out-Null
    git cherry-pick --abort 2>$null | Out-Null
    $activeBranch = (git symbolic-ref --quiet --short HEAD 2>$null).Trim()
    if ($activeBranch -and $activeBranch -ne $currentBranch) {
        git switch $currentBranch 2>$null | Out-Null
    }
    if ($script:tempBranchCreated) {
        git branch -D $tempBranch 2>$null | Out-Null
    }
    if ($script:stashed) {
        Write-Warning "Automatic merge failed. Your changes remain in stash: $stashName"
    }
}

try {
    $gitStatus = git status --porcelain
    if (-not [string]::IsNullOrWhiteSpace($gitStatus)) {
        git stash push --include-untracked --message $stashName | Out-Null
        $stashed = $true
        git switch -c $tempBranch | Out-Null
        $tempBranchCreated = $true
        git stash pop --index | Out-Null
        $stashed = $false
        git add -A
        git commit -m $commitMessage | Out-Null
        git switch $currentBranch | Out-Null
    }

    git pull --rebase --stat
    if ($LASTEXITCODE -ne 0) { throw "git pull --rebase failed." }

    if ($tempBranchCreated) {
        git cherry-pick -X theirs $tempBranch
        if ($LASTEXITCODE -ne 0) {
            Resolve-RemainingConflicts
            git cherry-pick --continue | Out-Null
        }
        git branch -D $tempBranch | Out-Null
        $tempBranchCreated = $false
    }

    $unmerged = git ls-files --unmerged
    if (-not [string]::IsNullOrWhiteSpace($unmerged)) {
        Resolve-RemainingConflicts
    }

    $unmerged = git ls-files --unmerged
    if (-not [string]::IsNullOrWhiteSpace($unmerged)) {
        throw "Automatic conflict resolution could not complete cleanly."
    }

    git push
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }

} catch {
    Invoke-Cleanup
    Write-Error $_
    exit 1
}
