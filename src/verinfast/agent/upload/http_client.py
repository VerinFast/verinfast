import httpx


class HttpClient:
    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.client = httpx.Client(http2=True, timeout=None)

    def get_upload_url(self, route, file_data):
        """Get pre-signed URL for upload"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.token}"
            }

            response = self.client.post(
                f"{self.config.baseUrl}/upload/{route}",
                headers=headers,
                json=file_data
            )

            if response.status_code != 200:
                self.log(msg=f"Failed to get upload URL: {response.text}", tag="ERROR")
                return None

            return response.text.strip('"')

        except Exception as e:
            self.log(msg=f"Error getting upload URL: {str(e)}", tag="ERROR")
            return None

    def upload_file(self, upload_url, file_data):
        """Upload file to pre-signed URL"""
        try:
            headers = {"Content-Type": "application/json"}
            response = self.client.put(
                upload_url,
                headers=headers,
                json=file_data
            )

            if response.status_code != 200:
                self.log(msg=f"Upload failed: {response.text}", tag="ERROR")
                return False

            return True

        except Exception as e:
            self.log(msg=f"Error uploading file: {str(e)}", tag="ERROR")
            return False

    def get_scan_id_url(self):
        """Get URL for scan ID"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.token}"
            }

            response = self.client.get(
                f"{self.config.baseUrl}/scan_id",
                headers=headers
            )

            if response.status_code != 200:
                self.log(msg=f"Failed to get scan ID URL: {response.text}", tag="ERROR")
                return None

            return response.text.strip('"')

        except Exception as e:
            self.log(msg=f"Error getting scan ID URL: {str(e)}", tag="ERROR")
            return None

    def fetch_scan_id(self, url, headers):
        """Fetch scan ID from URL"""
        try:
            response = self.client.get(
                f"{self.config.baseUrl}{url}",
                headers=headers
            )

            if response.status_code != 200:
                self.log(msg=f"Failed to fetch scan ID: {response.text}", tag="ERROR")
                return None

            return response.text.replace("'", "").replace('"', '')

        except Exception as e:
            self.log(msg=f"Error fetching scan ID: {str(e)}", tag="ERROR")
            return None
