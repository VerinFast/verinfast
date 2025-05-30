import httpx
from verinfast.config import Config
from importlib.metadata import version
from typing import Union


requestx = httpx.Client(http2=True, timeout=None)


def report(identifier: Union[str, int], config: Config, product: str):
    """
    License reporter reports back usage of some commercial features to help
    keep users safe.

    Keyword arguments:
    identifier - a string or an integer used to identify the unique run
    config - an agent config checked for commercial features
    product - a string indicating which licensed product is being used

    Specifically if user data is being uploaded by malicious services
    this function can identify them and record important signals including
    the baseurl of their command and control infrastructure.

    It does not upload any user data

    """
    try:
        if config.reportId != 0 or config.shouldUpload:
            headers = {
                "content-type": "application/json",
                "Accept-Charset": "UTF-8",
            }
            v = version("verinfast")
            data = {
                "baseurl": config.baseUrl,
                "ran_dependencies": config.runDependencies,
                "ran_git": config.runGit,
                "ran_scan": config.runScan,
                "ran_sizes": config.runSizes,
                "ran_stats": config.runStats,
                "uuid": identifier,
                "product": product,
                "version": v,
            }
            response = requestx.post(
                f"https://logger.verinfast.com/logger?license=true&product={str(product)}&version={str(v)}",
                json=data,
                headers=headers,
            )
            return response
        return False
    except:
        return False
