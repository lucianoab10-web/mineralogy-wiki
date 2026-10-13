# Obsidian source paths
$ObsidianMineralsPath = "C:\Users\Luciano\iCloudDrive\iCloud~md~obsidian\my-notes\compartidos\second-brain\markdowns\"
$ObsidianImagesPath   = "C:\Users\Luciano\iCloudDrive\iCloud~md~obsidian\my-notes\compartidos\second-brain\imagenes\"

# MkDocs repository paths
$MkDocsRepoPath = "C:\Users\Luciano\mineralogy-wiki\hooks"
$MkDocsDocsPath = Join-Path $MkDocsRepoPath "docs"
$MkDocsImagesPath = Join-Path $MkDocsDocsPath "imagenes"

# 1. Mirror the Obsidian markdowns into the MkDocs docs folder
robocopy $ObsidianMineralsPath $MkDocsDocsPath /MIR

# 2. Mirror the Obsidian images into the MkDocs docs/imagenes folder
robocopy $ObsidianImagesPath $MkDocsImagesPath /MIR

# 3. Convert Obsidian image wikilinks to standard markdown pointing to the imagenes folder
Get-ChildItem -Path $MkDocsDocsPath -Filter *.md -Recurse | ForEach-Object {
    $content = Get-Content -Path $_.FullName -Raw
    if (![string]::IsNullOrEmpty($content)) {
        # Transforms ![[image.jpg]] into ![image.jpg](imagenes/image.jpg)
        $newContent = [regex]::Replace($content, '!\[\[(.*?)\]\]', '![$1](imagenes/$1)')
        if ($content -cne $newContent) {
            Set-Content -Path $_.FullName -Value $newContent -NoNewline
        }
    }
}

# 4. Stage, commit, and push to GitHub
Set-Location -Path $MkDocsRepoPath
git add .
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "Vault update: $timestamp"
git push origin main
python -m mkdocs gh-deploy --force
