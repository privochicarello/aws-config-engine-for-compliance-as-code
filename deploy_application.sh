#!/bin/bash

export AWS_PAGER=""
export AWS_PROFILE="$1"
export AWS_DEFAULT_REGION="$2"

function usage() {
  echo -e "Usage: `basename $0` [AWS_PROFILE_NAME] [REGION]\n"
  echo -e "-h --help             Display this page"
  exit 0
}

if [ $# -ne 2 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    usage
fi

# Variables dependent on proper arguments
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

## add a check here. If we can't call the above command then the rest of the script won't work - so exit on error.

export BUCKET_NAME="compliance-engine-codebuild-source-$ACCOUNT_ID-$AWS_DEFAULT_REGION"

aws cloudformation deploy \
    --stack-name application-iam \
    --template-file application-account-iam.yaml \
    --no-fail-on-empty-changeset \
    --parameter-overrides ComplianceAccountId=$ACCOUNT_ID ForceDeploymentRoleInMainRegionOnly=force\
    --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy \
    --stack-name application \
    --template-file application-account-initial-setup.yaml \
    --parameter-overrides ComplianceAccountId=$ACCOUNT_ID \
    --no-fail-on-empty-changeset