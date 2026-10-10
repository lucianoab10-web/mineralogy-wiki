# Obsidian source path
$ObsidianMineralsPath = "C:\Users\Luciano\iCloudDrive\iCloud~md~obsidian\my-notes\compartidos\second-brain\markdowns\"

# MkDocs repository paths
$MkDocsRepoPath = "C:\Users\Luciano\mineralogy-wiki"
$MkDocsDocsPath = Join-Path $MkDocsRepoPath "docs"

# 1. Mirror the Obsidian folder into the MkDocs docs folder
robocopy $ObsidianMineralsPath $MkDocsDocsPath /MIR

# 2. Convert Obsidian image wikilinks ![[image.jpg]] to standard markdown ![image.jpg](image.jpg)
Get-ChildItem -Path $MkDocsDocsPath -Filter *.md -Recurse | ForEach-Object {
    $content = Get-Content -Path $_.FullName -Raw
    # Only run the regex replacement if the file is not empty
    if (![string]::IsNullOrEmpty($content)) {
        $newContent = [regex]::Replace($content, '!\[\[(.*?)\]\]', '![$1]($1)')
        if ($content -cne $newContent) {
            Set-Content -Path $_.FullName -Value $newContent -NoNewline
        }
    }
}

# 3. Stage, commit, and push to GitHub
Set-Location -Path $MkDocsRepoPath
git add .
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "Vault update: $timestamp"
git push origin main