#!/bin/bash

. settings.env

REGION=$MainRegion
ACCOUNT_ID=$ComplianceAccountId
COMPLIANCE_ACCOUNT_SOURCE_BUCKET=compliance-engine-codebuild-source-${ACCOUNT_ID}-${REGION}

zip ruleset.zip -r rules rulesets-build
aws s3 cp ruleset.zip s3://${COMPLIANCE_ACCOUNT_SOURCE_BUCKET}/
