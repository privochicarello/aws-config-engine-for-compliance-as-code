#!/bin/bash

ENV_VAR_FILE=settings.env

source $ENV_VAR_FILE

REGION=$MainRegion
ACCOUNT_ID=$ComplianceAccountId
COMPLIANCE_ACCOUNT_SOURCE_BUCKET=compliance-engine-codebuild-source-${ACCOUNT_ID}-${REGION}
PROFILE=$ComplianceAccountProfileName
COMPLIANCE_ACCOUNT_CODEPIPELINE_NAME=$CodePipelineComplianceEnginePipelineName

echo "[Deploy rdklib lambda layer]"

NAME_OF_THE_CHANGE_SET=$(aws serverlessrepo create-cloud-formation-change-set \
    --application-id arn:aws:serverlessrepo:ap-southeast-1:711761543063:applications/rdklib \
    --stack-name rdklib-Layer \
    --region ${REGION} \
    --profile ${PROFILE} \
    --query "ChangeSetId" | tr -d '\"')

## If there is an existing deployment and no changes, the ChangeSet will come to a failure state and execute-change-set will be failed.

aws cloudformation wait change-set-create-complete \
    --region ${REGION} \
    --profile ${PROFILE} \
    --change-set-name $NAME_OF_THE_CHANGE_SET

aws cloudformation execute-change-set \
    --region ${REGION} \
    --profile ${PROFILE} \
    --change-set-name $NAME_OF_THE_CHANGE_SET

echo "[Deploy Compliance Account]"

aws cloudformation deploy \
    --stack-name compliance-iam \
    --template-file compliance-account-iam.yaml \
    --parameter-overrides $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${REGION} \
    --profile ${PROFILE}

aws cloudformation deploy \
    --stack-name compliance-kms \
    --template-file compliance-account-kms-setup.yaml \
    --parameter-overrides $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --region ${REGION} \
    --profile ${PROFILE}

aws cloudformation deploy \
    --stack-name compliance \
    --template-file compliance-account-initial-setup.yaml \
    --parameter-overrides $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --region ${REGION} \
    --profile ${PROFILE}

aws cloudformation deploy \
    --stack-name compliance-kms \
    --template-file compliance-account-kms-setup.yaml \
    --parameter-overrides \
        GrantComplianceEngineAccess=true \
        $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --region ${REGION} \
    --profile ${PROFILE}

echo "[Build Rules and deployment scripts]"
zip ruleset.zip -r rules rulesets-build
aws s3 cp ruleset.zip s3://${COMPLIANCE_ACCOUNT_SOURCE_BUCKET}/ --region ${REGION} --profile ${PROFILE}

echo "[Wait 5 minute for the first codepipeline deployment to complete initialization in compliance account]"
echo "  - the codepipeline will fail for the first deployment due to application accounts have not yet setup"
sleep 300

aws cloudformation wait stack-exists --stack-name RDK-Config-Rule-Functions --region ${REGION} --profile ${PROFILE}
aws cloudformation wait stack-create-complete --stack-name RDK-Config-Rule-Functions --region ${REGION} --profile ${PROFILE}

## Compliance account can be application account and have rules being deployed.
echo "[Deploy Application Accounts]"

aws cloudformation deploy \
    --stack-name application-iam \
    --template-file application-account-iam.yaml \
    --parameter-overrides $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${REGION} \
    --profile ${PROFILE}

aws cloudformation deploy \
    --stack-name application \
    --template-file application-account-initial-setup.yaml \
    --parameter-overrides $(cat ${ENV_VAR_FILE}) \
    --no-fail-on-empty-changeset \
    --region ${REGION} \
    --profile ${PROFILE}

echo "[Deploy rules with CodePipeline]"
aws codepipeline start-pipeline-execution --name ${COMPLIANCE_ACCOUNT_CODEPIPELINE_NAME} --region ${REGION} --profile ${PROFILE}
