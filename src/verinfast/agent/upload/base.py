from .http_client import HttpClient
from .file_handler import FileHandler
from .validators import validate_upload_params, validate_route


class Uploader:
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config
        self.log = agent.log
        self.http_client = HttpClient(self.config, self.log)
        self.file_handler = FileHandler(self.config, self.log)

    def upload(self, route, file, source=None, isJSON=True):
        """Main upload method"""
        if not self.config.shouldUpload:
            return None

        try:
            # Validate route
            if not validate_route(route):
                self.log(msg=f"Invalid upload route: {route}", tag="ERROR")
                return None

            # Validate parameters
            if not validate_upload_params(route, file, self.log):
                return None

            # Process file
            file_data = self.file_handler.process_file(file, source, isJSON)
            if not file_data:
                return None

            # Get upload URL
            upload_url = self.http_client.get_upload_url(route, file_data)
            if not upload_url:
                return None

            # Perform upload
            success = self.http_client.upload_file(upload_url, file_data)
            if success:
                self.log(msg=f"Successfully uploaded {file}", tag="Upload")
                return upload_url

            return None

        except Exception as e:
            self.log(msg=f"Error in upload: {str(e)}", tag="ERROR")
            return None

    def get_scan_id(self):
        """Get scan ID for the current run"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.token}",
            }

            get_url = self.http_client.get_scan_id_url()
            if not get_url:
                return None

            scan_id = self.http_client.fetch_scan_id(get_url, headers)
            if scan_id:
                self.log(msg=scan_id, tag="Report Run Id", display=True)
                return scan_id

            return None

        except Exception as e:
            self.log(msg=f"Error getting scan ID: {str(e)}", tag="ERROR")
            return None
