import os
import json
from pathlib import Path
from uuid import uuid4
from .validators import validate_file_name


class FileHandler:
    def __init__(self, config, log):
        self.config = config
        self.log = log

    def process_file(self, file, source=None, isJSON=True):
        """Process file for upload"""
        try:
            if not os.path.exists(file):
                self.log(msg=f"File does not exist: {file}", tag="ERROR")
                return None

            file_path = Path(file)

            # Validate filename
            if not validate_file_name(file_path.name):
                self.log(msg=f"Invalid filename: {file_path.name}", tag="ERROR")
                return None

            file_size = os.path.getsize(file)

            # Generate metadata
            file_data = {
                "filename": file_path.name,
                "size": file_size,
                "id": str(uuid4()),
                "source": source or file_path.stem,
            }

            # Handle JSON files
            if isJSON:
                try:
                    with open(file, "r") as f:
                        content = json.load(f)
                    file_data["content"] = content
                except json.JSONDecodeError as e:
                    self.log(msg=f"Invalid JSON in file {file}: {str(e)}", tag="ERROR")
                    return None
                except Exception as e:
                    self.log(
                        msg=f"Error reading JSON file {file}: {str(e)}", tag="ERROR"
                    )
                    return None
            # Handle non-JSON files
            else:
                try:
                    with open(file, "r") as f:
                        content = f.read()
                    file_data["content"] = content
                except Exception as e:
                    self.log(msg=f"Error reading file {file}: {str(e)}", tag="ERROR")
                    return None

            # Add template data if available
            if hasattr(self.config, "template_data"):
                file_data["template"] = self.config.template_data

            return file_data

        except Exception as e:
            self.log(msg=f"Error processing file {file}: {str(e)}", tag="ERROR")
            return None

    def get_file_type(self, file_path):
        """Determine file type based on extension"""
        extension = Path(file_path).suffix.lower()

        if extension in [".json"]:
            return "json"
        elif extension in [".txt", ".log", ".md"]:
            return "text"
        elif extension in [".yml", ".yaml"]:
            return "yaml"
        else:
            return "binary"

    def validate_file_size(self, file_path, max_size_mb=100):
        """Check if file size is within limits"""
        try:
            size_bytes = os.path.getsize(file_path)
            size_mb = size_bytes / (1024 * 1024)

            if size_mb > max_size_mb:
                self.log(
                    msg=f"File {file_path} exceeds maximum size of {max_size_mb}MB",
                    tag="ERROR",
                )
                return False

            return True

        except Exception as e:
            self.log(msg=f"Error checking file size: {str(e)}", tag="ERROR")
            return False
