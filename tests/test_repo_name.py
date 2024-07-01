import json
from pathlib import Path
from verinfast.utils.utils import get_repo_name_url_and_branch

file_path = Path(__file__)
test_folder = file_path.parent.absolute()
fixtures_dir = test_folder.joinpath("fixtures").absolute()
url_list_path = str(
    fixtures_dir.joinpath('url_support/test_repo_urls.json').absolute()
)
with open(url_list_path, "r") as f:
    url_list = json.load(f)


def test_repo_urls():
    for url in url_list:
        repo_info = get_repo_name_url_and_branch(url["url"])
        repo_name = repo_info["repo_name"]
        repo_url = repo_info["repo_url"]
        branch = repo_info["branch"]
        assert repo_name == url["expected_name"], (
            f"Expected name: {url['expected_name']}, "
            f"Got: {repo_name} for {url['test']}"
        )
        assert repo_url == url["expected_url"], (
            f"Expected repo_url: {url['expected_url']}, "
            f"Got: {repo_url} for {url['test']}"
        )
        assert branch == url["expected_branch"], (
            f"Expected branch: {url['expected_branch']}, "
            f"Got: {branch} for {url['test']}"
        )
        print(f"Test passed for {url['test']}")
        print(f"Name: {repo_name}, URL: {repo_url}, Branch: {branch}")
