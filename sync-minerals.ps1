# Update this path to where your minerals folder lives in Obsidian
$ObsidianMineralsPath = "C:\Users\Luciano\iCloudDrive\iCloud~md~obsidian\my-notes\compartidos\second-brain\markdowns"

# MkDocs repository paths
$MkDocsRepoPath = "C:\Users\Luciano\mineralogy-wiki"
$MkDocsDocsPath = Join-Path $MkDocsRepoPath "docs"

# 1. Mirror the Obsidian folder into the MkDocs docs folder (deletes files in destination that were removed from source)
robocopy $ObsidianMineralsPath $MkDocsDocsPath /MIR

# 2. Convert Obsidian image wikilinks ![[image.jpg]] to standard markdown ![image.jpg](image.jpg)
Get-ChildItem -Path $MkDocsDocsPath -Filter *.md -Recurse | ForEach-Object {
    $content = Get-Content -Path $_.FullName -Raw
    $newContent = [regex]::Replace($content, '!\[\[(.*?)\]\]', '![$1]($1)')
    if ($content -cne $newContent) {
        Set-Content -Path $_.FullName -Value $newContent -NoNewline
    }
}

# 3. Stage, commit, and push to GitHub
Set-Location -Path $MkDocsRepoPath
git add .
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "Vault update: $timestamp"
git push origin main