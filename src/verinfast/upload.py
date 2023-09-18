def make_upload_path(
        path_type: str,
        report: str,
        code: int = None,
        repo_name: str = None
) -> str:
    paths = {
        "git": f"/report/{report}/CorsisCode/{code}/{repo_name}/git",
        "sizes": f"/report/{report}/CorsisCode/{code}/{repo_name}/sizes",
        "pygount": f"/report/{report}/CorsisCode/{code}/{repo_name}/pygount",
        "stats": f"/report/{report}/CorsisCode/{code}/{repo_name}/stats",
        "findings": f"/report/{report}/CorsisCode/{code}/{repo_name}/findings",
        "dependencies": f"/report/{report}/CorsisCode/{code}/{repo_name}/dependencies",  # noqa: E501
        "costs": f"/report/{report}/costs",
        "instances": f"/report/{report}/instances",
        "storage": f"/report/{report}/storage",
    }

    requires_code = [
        "git",
        "sizes",
        "pygount",
        "stats",
        "findings",
        "dependencies"
    ]

    if path_type in requires_code and code is None:
        raise Exception(f"Invocation Error: type {path_type} requires code")

    if path_type in requires_code and repo_name is None:
        raise Exception(f"Invocation Error: type {path_type} requires repo_name")  # noqa: E501

    return paths[path_type]
