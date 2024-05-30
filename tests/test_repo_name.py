from verinfast.utils.utils import get_repo_name_and_url

url_list = [
    {
        "url": "git@github.com:StartupOS/small-test-repo.git",
        "expected_name": "small-test-repo.git",
        "expected_url": "git@github.com:StartupOS/small-test-repo.git",
    },
    {
        "url": "git@github.com:StartupOS/small-test-repo.git@main",
        "expected_name": "small-test-repo.git@main",
        "expected_url": "git@github.com:StartupOS/small-test-repo.git"
    },
    {
        "url": "git.gitlab.foo.com:demo/demo.git",
        "expected_name": "demo.git",
        "expected_url": "git.gitlab.foo.com:demo/demo.git"
    },
]


def test_repo_urls():
    for url in url_list:
        name, repo_url = get_repo_name_and_url(url["url"])
        assert name == url["expected_name"]
        assert repo_url == url["expected_url"]
    return None
