#!/bin/bash
# Script to initialize git repository and push to GitHub

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Path to project directory
PROJECT_DIR="/home/jason/Documents/VideoSceneDetector"
GITHUB_REPO="https://github.com/jaywalked78/VideoSceneDetector.git"

echo -e "${YELLOW}Setting up GitHub repository for Video Scene Detector...${NC}"

# Change to project directory
cd $PROJECT_DIR || {
    echo -e "${RED}Failed to change to project directory: $PROJECT_DIR${NC}"
    exit 1
}

# Create .gitignore file
echo -e "${YELLOW}Creating .gitignore file...${NC}"
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# Authentication files
token.pickle
credentials.json

# Local configuration
.env

# Logs
*.log

# Video and image files
*.mp4
*.mov
*.avi
*.mkv
*.jpg
*.jpeg
*.png
*.gif
EOL

# Check if it's already a git repository
if [ -d .git ]; then
    echo -e "${YELLOW}Already a git repository, checking remote...${NC}"
    
    # Check if the remote is already set
    if git remote | grep -q "origin"; then
        current_remote=$(git remote get-url origin)
        if [ "$current_remote" != "$GITHUB_REPO" ]; then
            echo -e "${YELLOW}Updating remote URL from $current_remote to $GITHUB_REPO${NC}"
            git remote set-url origin $GITHUB_REPO
        else
            echo -e "${GREEN}Remote is already set correctly.${NC}"
        fi
    else
        echo -e "${YELLOW}Adding remote origin...${NC}"
        git remote add origin $GITHUB_REPO
    fi
else
    echo -e "${YELLOW}Initializing git repository...${NC}"
    git init
    
    echo -e "${YELLOW}Adding remote origin...${NC}"
    git remote add origin $GITHUB_REPO
fi

# Configure Git user information
echo -e "${YELLOW}Setting up Git user configuration...${NC}"
read -p "Enter your GitHub email: " git_email
read -p "Enter your GitHub username: " git_name

# Set git user configuration for this repository
git config user.email "$git_email"
git config user.name "$git_name"

echo -e "${GREEN}Git user configured as: $git_name <$git_email>${NC}"

# Add all files
echo -e "${YELLOW}Adding files to git...${NC}"
git add .

# Commit
echo -e "${YELLOW}Committing files...${NC}"
git commit -m "Initial commit of Video Scene Detector"

# Set the branch to main (GitHub's default)
echo -e "${YELLOW}Ensuring we're on the main branch...${NC}"
git branch -M main

# Push to GitHub
echo -e "${YELLOW}Pushing to GitHub...${NC}"
echo -e "${YELLOW}Note: You may be prompted for your GitHub username and password/token${NC}"
git push -u origin main

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Successfully pushed to GitHub!${NC}"
    echo -e "${GREEN}Repository URL: $GITHUB_REPO${NC}"
else
    echo -e "${RED}Failed to push to GitHub.${NC}"
    echo -e "${YELLOW}If you're using password authentication, note that GitHub no longer accepts passwords for Git operations.${NC}"
    echo -e "${YELLOW}Create a personal access token at: https://github.com/settings/tokens${NC}"
    echo -e "${YELLOW}Then use that token instead of your password when prompted.${NC}"
fi

exit 0 