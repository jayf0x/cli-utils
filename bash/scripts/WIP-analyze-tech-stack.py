#!/usr/bin/env python3
"""
Technology Stack LOC Analyzer
Analyzes lines of code written per technology/framework based on git history.
Outputs resume-ready technology statistics with package.json dependency detection.
"""

import subprocess
import re
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

# --------------------------
# CONFIG
# --------------------------
GITHUB_DIR = "~/Documents/GitHub"
OUTPUT_DIR = Path(__file__).parent

# FILL in to get personal info
YOUR_EMAIL_PATTERNS = [
    "*",
    "*",
]

# Repos to exclude from work analysis
EXCLUDE_REPOS = {}

# Auto-discover all repos (same as team-stats-resume.py)
WORK_REPOS = sorted([
    str(p) for p in Path(GITHUB_DIR).glob("*")
    if p.is_dir() and (p / ".git").exists() and p.name not in EXCLUDE_REPOS
])

# Personal projects
PERSONAL_REPOS = sorted([
    str(p) for p in Path(GITHUB_DIR).glob("*")
    if p.is_dir() 
    and (p / ".git").exists() 
    and not p.name.startswith(".")
    and p.name not in EXCLUDE_REPOS
])



# Filters (same as team-stats-resume.py)
IGNORE_MERGE_COMMITS = True
MAX_FILES_PER_COMMIT = 100  # Commits touching >100 files are likely mass changes
MAX_LOC_PER_FILE = 500      # Single file changes >500 lines are likely generated/refactors

# Only count source code file types
VALID_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".py", ".vue", ".css", ".scss", ".sass", ".sh"}

# Technology detection by file extension
TECH_PATTERNS = {
    # Frontend Frameworks
    "React": {
        "extensions": [".jsx", ".tsx"],
        "color": "🔵"
    },
    "Vue.js": {
        "extensions": [".vue"],
        "color": "🟢"
    },
    
    # Languages
    "TypeScript": {
        "extensions": [".ts", ".tsx"],
        "color": "🔷"
    },
    "JavaScript": {
        "extensions": [".js", ".jsx"],
        "color": "🟡"
    },
    "Python": {
        "extensions": [".py"],
        "color": "🐍"
    },
    "Bash/Shell": {
        "extensions": [".sh", ".bash"],
        "color": "🔨"
    },
    
    # Styling
    "CSS/SCSS": {
        "extensions": [".css", ".scss", ".sass", ".less"],
        "color": "🎨"
    },
}

# Package names to look for in package.json dependencies
# update to usage
PACKAGE_DETECTION = {
    # State Management
    "Zustand": ["zustand"],
    "Redux": ["redux", "@reduxjs/toolkit", "react-redux"],
    "MobX": ["mobx", "mobx-react"],
    "Jotai": ["jotai"],
    "Recoil": ["recoil"],
    
    # Data Fetching
    "TanStack Query": ["@tanstack/react-query", "@tanstack/query-core"],
    "SWR": ["swr"],
    "Apollo": ["@apollo/client", "apollo-client"],
    "RTK Query": ["@reduxjs/toolkit"],
    
    # UI Frameworks/Libraries
    "Chakra UI": ["@chakra-ui/react", "@chakra-ui/core"],
    "Material UI": ["@mui/material", "@material-ui/core"],
    "Ant Design": ["antd"],
    "Mantine": ["@mantine/core"],
    "Headless UI": ["@headlessui/react"],
    
    # CSS/Styling
    "Tailwind CSS": ["tailwindcss"],
    "Emotion": ["@emotion/react", "@emotion/styled"],
    "Styled Components": ["styled-components"],
    
    # Build Tools
    "Vite": ["vite"],
    "Webpack": ["webpack"],
    "Turbo": ["turbo"],
    "Lerna": ["lerna"],
    
    # Testing
    "Jest": ["jest"],
    "Vitest": ["vitest"],
    "Playwright": ["@playwright/test"],
    "Cypress": ["cypress"],
    "Testing Library": ["@testing-library/react"],
    
    # Backend/Services
    "Firebase": ["firebase"],
    "Supabase": ["@supabase/supabase-js"],
    
    # Module Federation
    "Module Federation": ["@module-federation/enhanced"],
    
    # Form Libraries
    "React Hook Form": ["react-hook-form"],
    "Formik": ["formik"],
    
    # Routing
    "React Router": ["react-router-dom", "react-router"],
    "TanStack Router": ["@tanstack/react-router"],
}


def run_git(repo_path, args):
    """Run git command and return output."""
    result = subprocess.run(
        ["git", "-C", repo_path] + args,
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_you(author):
    """Check if commit is from you."""
    return any(pattern.lower() in author.lower() for pattern in YOUR_EMAIL_PATTERNS)


def is_merge_commit(msg):
    """Check if commit is a merge."""
    return msg.lower().startswith("merge")


def is_valid_file(filepath):
    """Check if file has a valid source code extension."""
    ext = Path(filepath).suffix.lower()
    return ext in VALID_EXTENSIONS


def is_mass_change(num_files, file_changes):
    """
    Detect mass changes like prettier config updates or large merges.
    Returns True if this looks like a mass refactor/config change.
    """
    if num_files > MAX_FILES_PER_COMMIT:
        return True
    
    for added, deleted in file_changes:
        if added > MAX_LOC_PER_FILE or deleted > MAX_LOC_PER_FILE:
            return True
    
    return False


def get_file_extension(filepath):
    """Get normalized file extension."""
    return Path(filepath).suffix.lower()


def detect_packages(repo_path):
    """
    Scan package.json files in repo to detect frameworks/libraries used.
    Returns set of detected package names.
    """
    detected = set()
    repo_path = Path(repo_path)
    
    # Find all package.json files
    package_files = list(repo_path.glob("**/package.json"))
    
    for pkg_file in package_files:
        # Skip node_modules
        if "node_modules" in str(pkg_file):
            continue
        
        try:
            with open(pkg_file, 'r') as f:
                data = json.load(f)
                
            # Combine dependencies and devDependencies
            deps = {}
            deps.update(data.get("dependencies", {}))
            deps.update(data.get("devDependencies", {}))
            
            # Check each package we're looking for
            for package_name, npm_packages in PACKAGE_DETECTION.items():
                for npm_pkg in npm_packages:
                    if npm_pkg in deps:
                        detected.add(package_name)
                        break
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    
    return detected


def analyze_tech_stack(repos, category, since_date=None):
    """
    Analyze LOC by technology for given repositories.
    Applies same filtering as team-stats-resume.py (no merges, no mass changes).
    Returns: (tech_stats, packages_detected)
    """
    tech_stats = defaultdict(lambda: {
        "added": 0,
        "deleted": 0,
        "net": 0,
        "files": set(),
        "commits": 0,
    })
    
    all_packages = set()
    
    for repo_path in repos:
        repo_name = Path(repo_path).name
        
        if not Path(repo_path).exists():
            continue
        
        print(f"  📊 {repo_name}...")
        
        # Detect packages from package.json
        packages = detect_packages(repo_path)
        all_packages.update(packages)
        
        # Build git log command
        date_args = []
        if since_date:
            date_args.append(f"--since={since_date}")
        
        separator = "|||"
        log_cmd = [
            "log",
            f"--pretty=format:COMMIT:{separator}%an{separator}%s",
            "--numstat",
        ] + date_args
        
        output = run_git(str(repo_path), log_cmd)
        if not output:
            continue
        
        # Parse commits with filtering
        current_author = None
        current_msg = None
        current_files = []
        current_changes = []  # Track (added, deleted) per file
        
        for line in output.splitlines():
            if line.startswith(f"COMMIT:{separator}"):
                # Process previous commit
                if current_author and is_you(current_author):
                    # Apply filters (same as team-stats-resume.py)
                    skip = False
                    
                    if IGNORE_MERGE_COMMITS and is_merge_commit(current_msg):
                        skip = True
                    
                    if is_mass_change(len(current_files), current_changes):
                        skip = True
                    
                    if not skip:
                        # Count this commit's stats
                        for filepath, added, deleted in current_files:
                            ext = get_file_extension(filepath)
                            
                            # Find matching technology
                            for tech, config in TECH_PATTERNS.items():
                                if ext in config["extensions"]:
                                    tech_stats[tech]["added"] += added
                                    tech_stats[tech]["deleted"] += deleted
                                    tech_stats[tech]["net"] += (added - deleted)
                                    tech_stats[tech]["files"].add(f"{repo_name}/{filepath}")
                                    tech_stats[tech]["commits"] += 1
                
                # Parse new commit header
                parts = line.split(separator)
                if len(parts) >= 3:
                    current_author = parts[1]
                    current_msg = parts[2]
                    current_files = []
                    current_changes = []
            else:
                # Parse numstat line: added deleted filename
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    try:
                        added = int(parts[0]) if parts[0] != "-" else 0
                        deleted = int(parts[1]) if parts[1] != "-" else 0
                        filepath = parts[2]
                        
                        # Only count valid file extensions
                        if not is_valid_file(filepath):
                            continue
                        
                        current_files.append((filepath, added, deleted))
                        current_changes.append((added, deleted))
                    except ValueError:
                        continue
        
        # Process last commit
        if current_author and is_you(current_author):
            skip = False
            
            if IGNORE_MERGE_COMMITS and is_merge_commit(current_msg):
                skip = True
            
            if is_mass_change(len(current_files), current_changes):
                skip = True
            
            if not skip:
                for filepath, added, deleted in current_files:
                    ext = get_file_extension(filepath)
                    
                    for tech, config in TECH_PATTERNS.items():
                        if ext in config["extensions"]:
                            tech_stats[tech]["added"] += added
                            tech_stats[tech]["deleted"] += deleted
                            tech_stats[tech]["net"] += (added - deleted)
                            tech_stats[tech]["files"].add(f"{repo_name}/{filepath}")
                            tech_stats[tech]["commits"] += 1
    
    return tech_stats, all_packages


def format_number(num):
    """Format number with K suffix."""
    if abs(num) >= 10000:
        return f"{num/1000:.1f}K"
    elif abs(num) >= 1000:
        return f"{num/1000:.1f}K"
    else:
        return str(num)


def generate_report(work_stats, work_packages, personal_stats, personal_packages, period_name):
    """Generate formatted report with package detection."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"TECHNOLOGY STACK ANALYSIS - {period_name}")
    lines.append("=" * 80)
    lines.append("")
    
    # Work repositories
    lines.append("🏢 PROFESSIONAL WORK REPOSITORIES")
    lines.append("-" * 80)
    lines.append(f"Repositories analyzed: {len([p for p in WORK_REPOS if Path(p).exists()])}")
    lines.append(f"Filtering: No merges, no mass changes (>{MAX_FILES_PER_COMMIT} files or >{MAX_LOC_PER_FILE} LOC/file)")
    lines.append("")
    
    if work_stats:
        # Sort by net LOC
        sorted_tech = sorted(work_stats.items(), key=lambda x: x[1]["net"], reverse=True)
        
        lines.append(f"{'Technology':<20} {'Net LOC':<12} {'Added':<12} {'Deleted':<12} {'Files':<8}")
        lines.append("-" * 80)
        
        for tech, stats in sorted_tech:
            if stats["net"] > 0:  # Only show positive contributions
                color = TECH_PATTERNS.get(tech, {}).get("color", "")
                lines.append(
                    f"{color} {tech:<18} "
                    f"{format_number(stats['net']):<12} "
                    f"+{format_number(stats['added']):<11} "
                    f"-{format_number(stats['deleted']):<11} "
                    f"{len(stats['files']):<8}"
                )
        
        lines.append("")
        lines.append("📦 FRAMEWORKS & LIBRARIES (from package.json):")
        lines.append("-" * 80)
        
        if work_packages:
            # Categorize packages
            state_mgmt = ["Zustand", "Redux", "MobX", "Jotai", "Recoil"]
            data_fetch = ["TanStack Query", "SWR", "Apollo", "RTK Query"]
            ui_libs = ["Chakra UI", "Material UI", "Ant Design", "Mantine", "Headless UI"]
            styling = ["Tailwind CSS", "Emotion", "Styled Components"]
            build = ["Vite", "Webpack", "Turbo", "Lerna"]
            testing = ["Jest", "Vitest", "Playwright", "Cypress", "Testing Library"]
            forms = ["React Hook Form", "Formik"]
            routing = ["React Router", "TanStack Router"]
            
            categories = [
                ("State Management", state_mgmt),
                ("Data Fetching", data_fetch),
                ("UI Libraries", ui_libs),
                ("Styling", styling),
                ("Build Tools", build),
                ("Testing", testing),
                ("Forms", forms),
                ("Routing", routing),
            ]
            
            for cat_name, cat_packages in categories:
                found = [pkg for pkg in cat_packages if pkg in work_packages]
                if found:
                    lines.append(f"  {cat_name}: {', '.join(found)}")
            
            # Other packages not categorized above
            categorized = set([pkg for _, cat in categories for pkg in cat])
            other = sorted(work_packages - categorized)
            if other:
                lines.append(f"  Other: {', '.join(other)}")
        else:
            lines.append("  No package.json files found")
        
        lines.append("")
        lines.append("📊 RESUME-READY SUMMARY:")
        lines.append("-" * 80)
        
        # Build resume bullet points
        ts_lines = work_stats.get('TypeScript', {}).get('net', 0)
        react_lines = work_stats.get('React', {}).get('net', 0)
        vue_lines = work_stats.get('Vue.js', {}).get('net', 0)
        css_lines = work_stats.get('CSS/SCSS', {}).get('net', 0)
        python_lines = work_stats.get('Python', {}).get('net', 0)
        
        ts_files = len(work_stats.get('TypeScript', {}).get('files', set()))
        react_files = len(work_stats.get('React', {}).get('files', set()))
        
        if ts_lines > 0:
            lines.append(f"  • Wrote {format_number(ts_lines)}+ lines of TypeScript across {ts_files} files")
        if react_lines > 0:
            lines.append(f"  • Built React components with {format_number(react_lines)}+ lines of JSX/TSX code")
        if vue_lines > 0:
            lines.append(f"  • Maintained Vue.js applications with {format_number(vue_lines)}+ lines")
        if css_lines > 0:
            lines.append(f"  • Styled applications with {format_number(css_lines)}+ lines of CSS/SCSS")
        if python_lines > 0:
            lines.append(f"  • Automated workflows with {format_number(python_lines)}+ lines of Python")
        
        # Add framework experience
        if work_packages:
            key_frameworks = ["Zustand", "TanStack Query", "Chakra UI", "Tailwind CSS", "Module Federation"]
            used = [fw for fw in key_frameworks if fw in work_packages]
            if used:
                lines.append(f"  • Experience with: {', '.join(used)}")
        
    lines.append("")
    
    # Personal repositories
    lines.append("💻 PERSONAL PROJECTS")
    lines.append("-" * 80)
    lines.append(f"Repositories analyzed: {len([p for p in PERSONAL_REPOS if Path(p).exists()])}")
    lines.append("")
    
    if personal_stats:
        sorted_tech = sorted(personal_stats.items(), key=lambda x: x[1]["net"], reverse=True)
        
        lines.append(f"{'Technology':<20} {'Net LOC':<12} {'Added':<12} {'Deleted':<12} {'Files':<8}")
        lines.append("-" * 80)
        
        for tech, stats in sorted_tech:
            if stats["net"] > 0:
                color = TECH_PATTERNS.get(tech, {}).get("color", "")
                lines.append(
                    f"{color} {tech:<18} "
                    f"{format_number(stats['net']):<12} "
                    f"+{format_number(stats['added']):<11} "
                    f"-{format_number(stats['deleted']):<11} "
                    f"{len(stats['files']):<8}"
                )
        
        if personal_packages:
            lines.append("")
            lines.append("📦 Technologies Used:")
            lines.append("-" * 80)
            lines.append(f"  {', '.join(sorted(personal_packages))}")
    
    lines.append("")
    return "\n".join(lines)


def main():
    """Run analysis for multiple time periods."""
    today = datetime.now()
    
    print("🔍 Analyzing Technology Stack by LOC...")
    print(f"Personal repos: {len(PERSONAL_REPOS)} repositories")
    print(f"Filters: No merges, <{MAX_FILES_PER_COMMIT} files/commit, <{MAX_LOC_PER_FILE} LOC/file")
    print()
    
    periods = [
        ("last_6_months", "Last 6 Months", (today - timedelta(days=180)).strftime("%Y-%m-%d")),
        ("last_12_months", "Last 12 Months", (today - timedelta(days=365)).strftime("%Y-%m-%d")),
        ("all_time", "All Time", None),
    ]
    
    output_file = OUTPUT_DIR / "tech-stack-analysis.txt"
    
    with open(output_file, "w") as f:
        f.write("TECHNOLOGY STACK LOC ANALYSIS\n")
        f.write(f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Work Repositories: {len(WORK_REPOS)}\n")
        f.write(f"Personal Repositories: {len(PERSONAL_REPOS)}\n")
        f.write(f"File types counted: {', '.join(sorted(VALID_EXTENSIONS))}\n")
        f.write(f"Filters: No merge commits, no mass changes (>{MAX_FILES_PER_COMMIT} files or >{MAX_LOC_PER_FILE} LOC/file)\n")
        f.write("\n")
        
        for period_key, period_name, since_date in periods:
            print(f"📅 {period_name}...")
            
            print("  Professional repos...")
            work_stats, work_packages = analyze_tech_stack(WORK_REPOS, "work", since_date)
            
            print("  Personal repos...")
            personal_stats, personal_packages = analyze_tech_stack(PERSONAL_REPOS, "personal", since_date)
            
            report = generate_report(work_stats, work_packages, personal_stats, personal_packages, period_name)
            f.write(report)
            f.write("\n\n")
            
            print()
    
    print(f"✅ Report saved to: {output_file}")
    print()
    print("📊 Quick Summary:")
    print(f"  Work packages detected: {len(work_packages) if work_packages else 0}")
    print(f"  Personal packages detected: {len(personal_packages) if personal_packages else 0}")


if __name__ == "__main__":
    main()
