from pathlib import Path
import os
import shutil

from verinfast.utils.utils import checkDependency
from verinfast.cloud.aws.blocks import get_aws_blocks
from verinfast.cloud.aws.costs import get_aws_costs
from verinfast.cloud.azure.costs import runAzure
from verinfast.cloud.aws.get_profile import find_profile
from verinfast.cloud.aws.instances import get_instances as get_aws_instances
from verinfast.cloud.azure.instances import get_instances as get_az_instances
from verinfast.cloud.gcp.instances import get_instances as get_gcp_instances
from verinfast.cloud.azure.blocks import getBlocks as get_az_blocks
from verinfast.cloud.gcp.blocks import getBlocks as get_gcp_blocks


class CloudScanner:
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config
        self.log = agent.log

    def scanCloud(self, config=None):
        """Main cloud scanning method"""
        # Need to reset config if it has changed
        if config:
            self.config = config
        self.log(msg="", tag="Doing cloud scan", display=True)
        cloud_config = self.config.modules.cloud
        self.log(msg=cloud_config, tag="Cloud Config")

        if cloud_config is None:
            return

        for provider in cloud_config:
            try:
                self._scan_provider(provider)
            except Exception as e:
                self.log(tag="ERROR", msg="Error processing provider", display=True)
                self.log(tag="ERROR PROVIDER", msg=str(provider), display=True)
                self.log(tag="ERROR", msg=e, display=True)

    def _scan_provider(self, provider):
        """Handle scanning for a specific cloud provider"""
        if provider.provider == "aws":
            self._scan_aws(provider)
        elif provider.provider == "azure":
            self._scan_azure(provider)
        elif provider.provider == "gcp":
            self._scan_gcp(provider)


    def _scan_aws(self, provider):
        """Handle AWS scanning"""
        if not checkDependency("aws", "AWS Command-line tool"):
            return

        account_id = str(provider.account).replace("-", "")
        # Verify AWS profile access
        if find_profile(account_id, self.log) is None:
            self.log(
                tag=f"No matching AWS CLI profiles found for {provider.account}",
                msg="Account can't be scanned.",
                display=True,
                timestamp=False,
            )
            return
        else:
            self.log(
                tag="AWS account access confirmed",
                msg=account_id,
                display=True,
                timestamp=False,
            )
        # Costs
        aws_cost_file = get_aws_costs(
            targeted_account=account_id,
            start=provider.start,
            end=provider.end,
            profile=provider.profile,
            path_to_output=self.config.output_dir,
            log=self.log,
            dry=self.config.dry,
        )
        if aws_cost_file:
            self.log(msg=aws_cost_file, tag="AWS Costs")
            self.agent.upload(file=aws_cost_file, route="costs", source="AWS")
        # Instances
        aws_instance_file = get_aws_instances(
            sub_id=account_id,
            path_to_output=self.config.output_dir,
            dry=self.config.dry,
        )
        if aws_instance_file:
            self.log(msg=aws_instance_file, tag="AWS Instances")
            self.agent.upload(file=aws_instance_file, route="instances", source="AWS")
        # Utilization
        aws_utilization_file = os.path.join(
            self.config.output_dir, f"aws-instances-{account_id}-utilization.json"
        )
        if Path(aws_utilization_file).is_file():
            self.agent.upload(
                file=aws_utilization_file, route="utilization", source="AWS"
            )
        # Storage blocks
        aws_block_file = get_aws_blocks(
            sub_id=account_id,
            path_to_output=self.config.output_dir,
            log=self.log,
            dry=self.config.dry,
        )
        if aws_block_file:
            self.log(msg=aws_block_file, tag="AWS Storage")
            self.agent.upload(file=aws_block_file, route="storage", source="AWS")

    def _scan_azure(self, provider):
        """Handle Azure scanning"""
        if not checkDependency("az", "Azure Command-line tool"):
            return
        # Costs
        azure_cost_file = runAzure(
            subscription_id=provider.account,
            start=provider.start,
            end=provider.end,
            path_to_output=self.config.output_dir,
            log=self.log,
            dry=self.config.dry,
        )
        if azure_cost_file:
            self.log(msg=azure_cost_file, tag="Azure Costs")
            self.agent.upload(file=azure_cost_file, route="costs", source="Azure")
        # Instances
        azure_instance_file = get_az_instances(
            sub_id=provider.account,
            path_to_output=self.config.output_dir,
            dry=self.config.dry,
            log=self.log,
        )
        if azure_instance_file:
            self.log(msg=azure_instance_file, tag="Azure instances")
            self.agent.upload(
                file=azure_instance_file, route="instances", source="Azure"
            )
        # Utilization
        azure_utilization_file = os.path.join(
            self.config.output_dir, f"az-instances-{provider.account}-utilization.json"
        )
        if Path(azure_utilization_file).is_file():
            self.agent.upload(
                file=azure_utilization_file, route="utilization", source="Azure"
            )
        # Storage blocks
        azure_block_file = get_az_blocks(
            sub_id=provider.account,
            path_to_output=self.config.output_dir,
            dry=self.config.dry,
        )
        if azure_block_file:
            self.log(msg=azure_block_file, tag="Azure Storage")
            self.agent.upload(file=azure_block_file, route="storage", source="Azure")

    def _scan_gcp(self, provider):
        """Handle GCP scanning"""
        if not checkDependency("gcloud", "Google Command-line tool"):
            return
        # Instances
        gcp_instance_file = get_gcp_instances(
            sub_id=provider.account,
            path_to_output=self.config.output_dir,
            dry=self.config.dry,
        )
        if gcp_instance_file:
            self.log(msg=gcp_instance_file, tag="GCP instances")
            self.agent.upload(file=gcp_instance_file, route="instances", source="GCP")
        # Utilization
        gcp_utilization_file = os.path.join(
            self.config.output_dir, f"gcp-instances-{provider.account}-utilization.json"
        )
        if Path(gcp_utilization_file).is_file():
            self.agent.upload(
                file=gcp_utilization_file, route="utilization", source="GCP"
            )
        # Storage blocks
        gcp_block_file = get_gcp_blocks(
            sub_id=provider.account,
            path_to_output=self.config.output_dir,
            dry=self.config.dry,
        )
        if gcp_block_file:
            self.log(msg=gcp_block_file, tag="GCP Storage")
            self.agent.upload(file=gcp_block_file, route="storage", source="GCP")
