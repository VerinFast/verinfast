from verinfast.utils.utils import get_repo_name_url_and_branch

url_list = [
    {
        "url": "git@github.com:StartupOS/small-test-repo.git",
        "expected_name": "small-test-repo.git",
        "expected_url": "git@github.com:StartupOS/small-test-repo.git",
        "expected_branch": None,
        "test": "Simple GitHub SSH URL"
    },
    {
        "url": "git@github.com:StartupOS/small-test-repo.git@develop",
        "expected_name": "small-test-repo.git",
        "expected_url": "git@github.com:StartupOS/small-test-repo.git",
        "expected_branch": "develop",
        "test": "GitHub SSH URL with branch"
    },
    {
        "url": "git@github.com:StartupOS/small-test-repo.git@"
               "test/slashes/inbranch",
        "expected_name": "small-test-repo.git",
        "expected_url": "git@github.com:StartupOS/small-test-repo.git",
        "expected_branch": "test/slashes/inbranch",
        "test": "GitHub SSH URL with branch with slashes"
    },
    {
        "url": "git@gitlab.com:gitlab-org/gitlab-foss.git",
        "expected_name": "gitlab-foss.git",
        "expected_url": "git@gitlab.com:gitlab-org/gitlab-foss.git",
        "expected_branch": None,
        "test": "Simple GitLab SSH URL"
    },
    {
        "url": "git@gitlab.com:gitlab-org/gitlab-foss.git@develop",
        "expected_name": "gitlab-foss.git",
        "expected_url": "git@gitlab.com:gitlab-org/gitlab-foss.git",
        "expected_branch": "develop",
        "test": "GitLab SSH URL with branch"
    },
    {
        "url": "git@ssh.dev.azure.com:v3/bar/Foo%20Mobile%20Android",
        "expected_name": "Foo%20Mobile%20Android",
        "expected_url": "git@ssh.dev.azure.com:v3/bar/"
                        "Foo%20Mobile%20Android",
        "expected_branch": None,
        "test": "Azure DevOps SSH URL"
    },
    {
        "url": "https://github.com/StartupOS/small-test-repo.git",
        "expected_name": "small-test-repo.git",
        "expected_url": "https://github.com/StartupOS/small-test-repo.git",
        "expected_branch": None,
        "test": "Simple GitHub HTTPS URL"
    },
    {
        "url": "https://github.com/StartupOS/small-test-repo.git@develop",
        "expected_name": "small-test-repo.git",
        "expected_url": "https://github.com/StartupOS/small-test-repo.git",
        "expected_branch": "develop",
        "test": "Simple GitHub HTTPS URL with branch"
    },
    {
        "url": "https://github.com/StartupOS/small-test-repo.git@test/"
               "slashes/inbranch",
        "expected_name": "small-test-repo.git",
        "expected_url": "https://github.com/StartupOS/small-test-repo.git",
        "expected_branch": "test/slashes/inbranch",
        "test": "GitHub HTTPS URL with branch with slashes"
    },
    {
        "url": "https://gitlab.com/gitlab-org/gitlab.git",
        "expected_name": "gitlab.git",
        "expected_url": "https://gitlab.com/gitlab-org/gitlab.git",
        "expected_branch": None,
        "test": "Simple GitLab HTTPS URL"
    },
    {
        "url": "https://gitlab.com/gitlab-org/gitlab.git@develop",
        "expected_name": "gitlab.git",
        "expected_url": "https://gitlab.com/gitlab-org/gitlab.git",
        "expected_branch": "develop",
        "test": "Simple GitLab HTTPS URL with branch"
    },
    {
        "url": "https://bitbucket.org/foo/bar.git",
        "expected_name": "bar.git",
        "expected_url": "https://bitbucket.org/foo/bar.git",
        "expected_branch": None,
        "test": "Simple Bitbucket HTTPS URL"
    },
    {
        "url": "https://bitbucket.org/foo/bar.git@develop",
        "expected_name": "bar.git",
        "expected_url": "https://bitbucket.org/foo/bar.git",
        "expected_branch": "develop",
        "test": "Simple Bitbucket HTTPS URL with branch"
    }
]


def test_repo_urls():
    for url in url_list:
        name, repo_url, branch = get_repo_name_url_and_branch(url["url"])
        assert name == url["expected_name"], (
            f"Expected name: {url['expected_name']}, "
            f"Got: {name} for {url['test']}"
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
        print(f"Name: {name}, URL: {repo_url}, Branch: {branch}")
