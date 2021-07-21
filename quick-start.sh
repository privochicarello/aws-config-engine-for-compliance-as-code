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
export BUCKET_NAME="compliance-engine-codebuild-source-$ACCOUNT_ID-$REGION"

echo "[Deploy rdklib lambda layer]"

NAME_OF_THE_CHANGE_SET=$(aws serverlessrepo create-cloud-formation-change-set \
    --application-id arn:aws:serverlessrepo:ap-southeast-1:711761543063:applications/rdklib \
    --stack-name rdklib-Layer \
    --query "ChangeSetId" | tr -d '\"')

aws cloudformation wait change-set-create-complete --change-set-name $NAME_OF_THE_CHANGE_SET

aws cloudformation execute-change-set --change-set-name $NAME_OF_THE_CHANGE_SET

echo "[Deploy Compliance Account]"

aws cloudformation deploy \
    --stack-name compliance-iam \
    --template-file compliance-account-iam.yaml \
    --parameter-overrides ComplianceAccountId=$ACCOUNT_ID \
    --no-fail-on-empty-changeset \
    --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy \
    --stack-name compliance-engine \
    --template-file compliance-account-initial-setup.yaml \
    --parameter-overrides ComplianceAccountId=$ACCOUNT_ID ApplicationAccountIds=$ACCOUNT_ID\
    --no-fail-on-empty-changeset

echo "[Build Rules and deployment scripts]"
zip ruleset.zip -r rules rulesets-build
aws s3 cp ruleset.zip s3://${COMPLIANCE_ACCOUNT_SOURCE_BUCKET}/

echo "[Waiting 5 minutes for the first CodePipeline run to complete initialization...]"
sleep 300

aws cloudformation wait stack-exists --stack-name RDK-Config-Rule-Functions
aws cloudformation wait stack-create-complete --stack-name RDK-Config-Rule-Functions

## Compliance account can be application account and have rules being deployed.
echo "[Deploy Application Accounts]"

aws cloudformation deploy \
    --stack-name application-iam \
    --template-file application-account-iam.yaml \
    --no-fail-on-empty-changeset \
    --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy \
    --stack-name application \
    --template-file application-account-initial-setup.yaml \
    --no-fail-on-empty-changeset

echo "[Deploy rules with CodePipeline]"
aws codepipeline start-pipeline-execution --name ${BUCKET_NAME}
