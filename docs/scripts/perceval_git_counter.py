#! /usr/bin/env python3

import argparse
from perceval.backends.core.git import Git

parser = argparse.ArgumentParser(description = "Count commits in a git repo")
parser.add_argument("repo", help = "Repository url")
parser.add_argument("dir", help = "Directory for cloning the repository")
parser.add_argument("--print", action='store_true', help = "Print hashes")
args = parser.parse_args()

repo = Git(uri=args.repo, gitpath=args.dir)
count = 0
for commit in repo.fetch():
    if args.print:
        print(commit['data']['commit'])
    count += 1
print("Number of commmits: %d." % count)
