# Copyright 2017-2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the License is located at
#
#        http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for
# the specific language governing permissions and limitations under the License.
'''
#####################################
##           Gherkin               ##
#####################################

 Rule Name:
   iam-group-no-policy-full-star

 Description:
   Check whether IAM Groups have an IAM policy with all permission enabled (or "Action:*"). IAM Policy includes the AWS-managed policy named AdministratorAccess, Customer-managed policies and inline policies.

 Trigger:
   Configuration Change on AWS::IAM::Group

 Reports on:
   AWS::IAM::Group

 Rule Parameters:
   None

 Feature:
   In order to: ensure that policies attached to any group does not have full administrative privileges
            As: a Security Officer
        I want: to ensure that no policy have "*" in their action.

 Scenarios:
   Scenario 1:
     Given: Any allow <Policy> statements of group has Action as "*"
      Then: Return NON_COMPLIANT

   Scenario 2:
     Given: All allow <Policy> statments of group do not have Action as "*"
      Then: Return COMPLIANT

   Scenario 3:
     Given: No policy is applying to the group
      Then: Return COMPLIANT

   Examples:
       |                Policy                      |
       | inline policy                              |
       | aws-managed predefined policy 		        |
       | customer-managed defined policy 	        |
'''
import json
import datetime
import boto3
import botocore

##############
# Parameters #
##############

# Define the default resource to report to Config Rules
DEFAULT_RESOURCE_TYPE = 'AWS::IAM::Group'

# Set to True to get the lambda to assume the Role attached on the Config Service (useful for cross-account).
ASSUME_ROLE_MODE = True

#############
# Main Code #
#############

def evaluate_compliance(event, configuration_item, valid_rule_parameters):
    """Form the evaluation(s) to be return to Config Rules

    Return either:
    None -- when no result needs to be displayed
    a string -- either COMPLIANT, NON_COMPLIANT or NOT_APPLICABLE
    a dictionary -- the evaluation dictionary, usually built by build_evaluation_from_config_item()
    a list of dictionary -- a list of evaluation dictionary , usually built by build_evaluation()

    Keyword arguments:
    event -- the event variable given in the lambda handler
    configuration_item -- the configurationItem dictionary in the invokingEvent
    valid_rule_parameters -- the output of the evaluate_parameters() representing validated parameters of the Config Rule

    Advanced Notes:
    1 -- if a resource is deleted and generate a configuration change with ResourceDeleted status, the Boilerplate code will put a NOT_APPLICABLE on this resource automatically.
    2 -- if a None or a list of dictionary is returned, the old evaluation(s) which are not returned in the new evaluation list are returned as NOT_APPLICABLE by the Boilerplate code
    3 -- if None or an empty string, list or dict is returned, the Boilerplate code will put a "shadow" evaluation to feedback that the evaluation took place properly
    """

    group_name = configuration_item['configuration']['groupName']
    iam_client = get_client('iam', event)

    # Inline policies
    inline_policy_names = get_all_group_inline_policy_names(iam_client, group_name)
    for policy_name in inline_policy_names:
        policy_document = iam_client.get_group_policy(GroupName=group_name, PolicyName=policy_name)['PolicyDocument']
        if is_statements_include_full_star_allow(policy_document['Statement']):
            return build_evaluation_from_config_item(configuration_item, "NON_COMPLIANT", annotation='An inline policy "' + policy_name + '" attached to the group "' + group_name + '" has full star allow permissions.')

    # Managed policies
    managed_policy_arn_and_name = get_all_group_managed_policy_arn_and_name(iam_client, group_name)
    for policy_arn, policy_name in managed_policy_arn_and_name.items():
        get_policy = iam_client.get_policy(PolicyArn=policy_arn)
        version = get_policy['Policy']['DefaultVersionId']
        get_policy_version = iam_client.get_policy_version(PolicyArn=policy_arn, VersionId=version)
        if is_statements_include_full_star_allow(get_policy_version['PolicyVersion']['Document']['Statement']):
            return build_evaluation_from_config_item(configuration_item, "NON_COMPLIANT", annotation='A managed policy with name "' + policy_name + '" attached to the group "' + group_name + '" has full star allow permissions.')

    return "COMPLIANT"

def get_all_group_inline_policy_names(iam_client, group_name):
    all_group_inline_policies = []
    list_policy_names = iam_client.list_group_policies(GroupName=group_name, MaxItems=1000)
    while True:
        all_group_inline_policies += list_policy_names['PolicyNames']
        if 'Marker' in list_policy_names:
            list_policy_names = iam_client.list_group_policies(GroupName=group_name, MaxItems=1000, Marker=list_policy_names['Marker'])
        else:
            break
    return all_group_inline_policies

def get_all_group_managed_policy_arn_and_name(iam_client, group_name):
    all_group_managed_policies_arn_and_name = {}
    list_policy_arn = iam_client.list_attached_group_policies(GroupName=group_name, MaxItems=1000)
    while True:
        for policy_dict in list_policy_arn['AttachedPolicies']:
            all_group_managed_policies_arn_and_name[policy_dict['PolicyArn']] = policy_dict['PolicyName']
        if 'Marker' in list_policy_arn:
            list_policy_arn = iam_client.list_attached_group_policies(GroupName=group_name, MaxItems=1000, Marker=list_policy_arn['Marker'])
        else:
            break
    return all_group_managed_policies_arn_and_name

def is_statements_include_full_star_allow(statements):
    statement_list = []
    if isinstance(statements, dict):
        statement_list = [statements]
    elif isinstance(statements, list):
        statement_list = statements
    else:
        print("Not recognized statement type:")
        print(statements)
        return False
    
    for statement in statement_list:        
        if statement['Effect'] == 'Deny':
            continue

        if 'Action' not in statement:
            print("No 'Action' in statement")
            print(statement)
            continue

        if isinstance(statement['Action'], list):
            for action in statement['Action']:
                if action == "*":
                    return True
        else:
            if statement['Action'] == "*":
                return True
    return False

def evaluate_parameters(rule_parameters):
    """Evaluate the rule parameters dictionary validity. Raise a ValueError for invalid parameters.

    Return:
    anything suitable for the evaluate_compliance()

    Keyword arguments:
    rule_parameters -- the Key/Value dictionary of the Config Rules parameters
    """
    valid_rule_parameters = rule_parameters
    return valid_rule_parameters

####################
# Helper Functions #
####################

# Build an error to be displayed in the logs when the parameter is invalid.
def build_parameters_value_error_response(ex):
    """Return an error dictionary when the evaluate_parameters() raises a ValueError.

    Keyword arguments:
    ex -- Exception text
    """
    return  build_error_response(internalErrorMessage="Parameter value is invalid",
                                 internalErrorDetails="An ValueError was raised during the validation of the Parameter value",
                                 customerErrorCode="InvalidParameterValueException",
                                 customerErrorMessage=str(ex))

# This gets the client after assuming the Config service role
# either in the same AWS account or cross-account.
def get_client(service, event):
    """Return the service boto client. It should be used instead of directly calling the client.

    Keyword arguments:
    service -- the service name used for calling the boto.client()
    event -- the event variable given in the lambda handler
    """
    if not ASSUME_ROLE_MODE:
        return boto3.client(service)
    credentials = get_assume_role_credentials(event["executionRoleArn"])
    return boto3.client(service, aws_access_key_id=credentials['AccessKeyId'],
                        aws_secret_access_key=credentials['SecretAccessKey'],
                        aws_session_token=credentials['SessionToken']
                       )

# This generate an evaluation for config
def build_evaluation(resource_id, compliance_type, event, resource_type=DEFAULT_RESOURCE_TYPE, annotation=None):
    """Form an evaluation as a dictionary. Usually suited to report on scheduled rules.

    Keyword arguments:
    resource_id -- the unique id of the resource to report
    compliance_type -- either COMPLIANT, NON_COMPLIANT or NOT_APPLICABLE
    event -- the event variable given in the lambda handler
    resource_type -- the CloudFormation resource type (or AWS::::Account) to report on the rule (default DEFAULT_RESOURCE_TYPE)
    annotation -- an annotation to be added to the evaluation (default None)
    """
    eval_cc = {}
    if annotation:
        eval_cc['Annotation'] = annotation
    eval_cc['ComplianceResourceType'] = resource_type
    eval_cc['ComplianceResourceId'] = resource_id
    eval_cc['ComplianceType'] = compliance_type
    eval_cc['OrderingTimestamp'] = str(json.loads(event['invokingEvent'])['notificationCreationTime'])
    return eval_cc

def build_evaluation_from_config_item(configuration_item, compliance_type, annotation=None):
    """Form an evaluation as a dictionary. Usually suited to report on configuration change rules.

    Keyword arguments:
    configuration_item -- the configurationItem dictionary in the invokingEvent
    compliance_type -- either COMPLIANT, NON_COMPLIANT or NOT_APPLICABLE
    annotation -- an annotation to be added to the evaluation (default None)
    """
    eval_ci = {}
    if annotation:
        eval_ci['Annotation'] = annotation
    eval_ci['ComplianceResourceType'] = configuration_item['resourceType']
    eval_ci['ComplianceResourceId'] = configuration_item['resourceId']
    eval_ci['ComplianceType'] = compliance_type
    eval_ci['OrderingTimestamp'] = configuration_item['configurationItemCaptureTime']
    return eval_ci

####################
# Boilerplate Code #
####################

# Helper function used to validate input
def check_defined(reference, reference_name):
    if not reference:
        raise Exception('Error: ', reference_name, 'is not defined')
    return reference

# Check whether the message is OversizedConfigurationItemChangeNotification or not
def is_oversized_changed_notification(message_type):
    check_defined(message_type, 'messageType')
    return message_type == 'OversizedConfigurationItemChangeNotification'

# Check whether the message is a ScheduledNotification or not.
def is_scheduled_notification(message_type):
    check_defined(message_type, 'messageType')
    return message_type == 'ScheduledNotification'

# Get configurationItem using getResourceConfigHistory API
# in case of OversizedConfigurationItemChangeNotification
def get_configuration(resource_type, resource_id, configuration_capture_time):
    result = AWS_CONFIG_CLIENT.get_resource_config_history(
        resourceType=resource_type,
        resourceId=resource_id,
        laterTime=configuration_capture_time,
        limit=1)
    configurationItem = result['configurationItems'][0]
    return convert_api_configuration(configurationItem)

# Convert from the API model to the original invocation model
def convert_api_configuration(configurationItem):
    for k, v in configurationItem.items():
        if isinstance(v, datetime.datetime):
            configurationItem[k] = str(v)
    configurationItem['awsAccountId'] = configurationItem['accountId']
    configurationItem['ARN'] = configurationItem['arn']
    configurationItem['configurationStateMd5Hash'] = configurationItem['configurationItemMD5Hash']
    configurationItem['configurationItemVersion'] = configurationItem['version']
    configurationItem['configuration'] = json.loads(configurationItem['configuration'])
    if 'relationships' in configurationItem:
        for i in range(len(configurationItem['relationships'])):
            configurationItem['relationships'][i]['name'] = configurationItem['relationships'][i]['relationshipName']
    return configurationItem

# Based on the type of message get the configuration item
# either from configurationItem in the invoking event
# or using the getResourceConfigHistiry API in getConfiguration function.
def get_configuration_item(invokingEvent):
    check_defined(invokingEvent, 'invokingEvent')
    if is_oversized_changed_notification(invokingEvent['messageType']):
        configurationItemSummary = check_defined(invokingEvent['configurationItemSummary'], 'configurationItemSummary')
        return get_configuration(configurationItemSummary['resourceType'], configurationItemSummary['resourceId'], configurationItemSummary['configurationItemCaptureTime'])
    elif is_scheduled_notification(invokingEvent['messageType']):
        return None
    return check_defined(invokingEvent['configurationItem'], 'configurationItem')

# Check whether the resource has been deleted. If it has, then the evaluation is unnecessary.
def is_applicable(configurationItem, event):
    try:
        check_defined(configurationItem, 'configurationItem')
        check_defined(event, 'event')
    except:
        return True
    status = configurationItem['configurationItemStatus']
    eventLeftScope = event['eventLeftScope']
    if status == 'ResourceDeleted':
        print("Resource Deleted, setting Compliance Status to NOT_APPLICABLE.")
    return (status == 'OK' or status == 'ResourceDiscovered') and not eventLeftScope

def get_assume_role_credentials(role_arn):
    sts_client = boto3.client('sts')
    try:
        assume_role_response = sts_client.assume_role(RoleArn=role_arn, RoleSessionName="configLambdaExecution")
        return assume_role_response['Credentials']
    except botocore.exceptions.ClientError as ex:
        # Scrub error message for any internal account info leaks
        print(str(ex))
        if 'AccessDenied' in ex.response['Error']['Code']:
            ex.response['Error']['Message'] = "AWS Config does not have permission to assume the IAM role."
        else:
            ex.response['Error']['Message'] = "InternalError"
            ex.response['Error']['Code'] = "InternalError"
        raise ex

# This removes older evaluation (usually useful for periodic rule not reporting on AWS::::Account).
def clean_up_old_evaluations(latest_evaluations, event):

    cleaned_evaluations = []

    old_eval = AWS_CONFIG_CLIENT.get_compliance_details_by_config_rule(
        ConfigRuleName=event['configRuleName'],
        ComplianceTypes=['COMPLIANT', 'NON_COMPLIANT'],
        Limit=100)

    old_eval_list = []

    while True:
        for old_result in old_eval['EvaluationResults']:
            old_eval_list.append(old_result)
        if 'NextToken' in old_eval:
            next_token = old_eval['NextToken']
            old_eval = AWS_CONFIG_CLIENT.get_compliance_details_by_config_rule(
                ConfigRuleName=event['configRuleName'],
                ComplianceTypes=['COMPLIANT', 'NON_COMPLIANT'],
                Limit=100,
                NextToken=next_token)
        else:
            break

    for old_eval in old_eval_list:
        old_resource_id = old_eval['EvaluationResultIdentifier']['EvaluationResultQualifier']['ResourceId']
        newer_founded = False
        for latest_eval in latest_evaluations:
            if old_resource_id == latest_eval['ComplianceResourceId']:
                newer_founded = True
        if not newer_founded:
            cleaned_evaluations.append(build_evaluation(old_resource_id, "NOT_APPLICABLE", event))

    return cleaned_evaluations + latest_evaluations

# This decorates the lambda_handler in rule_code with the actual PutEvaluation call
def lambda_handler(event, context):

    global AWS_CONFIG_CLIENT

    #print(event)
    check_defined(event, 'event')
    invoking_event = json.loads(event['invokingEvent'])
    rule_parameters = {}
    if 'ruleParameters' in event:
        rule_parameters = json.loads(event['ruleParameters'])

    try:
        valid_rule_parameters = evaluate_parameters(rule_parameters)
    except ValueError as ex:
        return build_parameters_value_error_response(ex)

    try:
        AWS_CONFIG_CLIENT = get_client('config', event)
        if invoking_event['messageType'] in ['ConfigurationItemChangeNotification', 'ScheduledNotification', 'OversizedConfigurationItemChangeNotification']:
            configuration_item = get_configuration_item(invoking_event)
            if is_applicable(configuration_item, event):
                compliance_result = evaluate_compliance(event, configuration_item, valid_rule_parameters)
            else:
                compliance_result = "NOT_APPLICABLE"
        else:
            return build_internal_error_response('Unexpected message type', str(invoking_event))
    except botocore.exceptions.ClientError as ex:
        if is_internal_error(ex):
            return build_internal_error_response("Unexpected error while completing API request", str(ex))
        return build_error_response("Customer error while making API request", str(ex), ex.response['Error']['Code'], ex.response['Error']['Message'])
    except ValueError as ex:
        return build_internal_error_response(str(ex), str(ex))

    evaluations = []
    latest_evaluations = []

    if not compliance_result:
        latest_evaluations.append(build_evaluation(event['accountId'], "NOT_APPLICABLE", event, resource_type='AWS::::Account'))
        evaluations = clean_up_old_evaluations(latest_evaluations, event)
    elif isinstance(compliance_result, str):
        if configuration_item:
            evaluations.append(build_evaluation_from_config_item(configuration_item, compliance_result))
        else:
            evaluations.append(build_evaluation(event['accountId'], compliance_result, event, resource_type=DEFAULT_RESOURCE_TYPE))
    elif isinstance(compliance_result, list):
        for evaluation in compliance_result:
            missing_fields = False
            for field in ('ComplianceResourceType', 'ComplianceResourceId', 'ComplianceType', 'OrderingTimestamp'):
                if field not in evaluation:
                    print("Missing " + field + " from custom evaluation.")
                    missing_fields = True

            if not missing_fields:
                latest_evaluations.append(evaluation)
        evaluations = clean_up_old_evaluations(latest_evaluations, event)
    elif isinstance(compliance_result, dict):
        missing_fields = False
        for field in ('ComplianceResourceType', 'ComplianceResourceId', 'ComplianceType', 'OrderingTimestamp'):
            if field not in compliance_result:
                print("Missing " + field + " from custom evaluation.")
                missing_fields = True
        if not missing_fields:
            evaluations.append(compliance_result)
    else:
        evaluations.append(build_evaluation_from_config_item(configuration_item, 'NOT_APPLICABLE'))

    # Put together the request that reports the evaluation status
    resultToken = event['resultToken']
    testMode = False
    if resultToken == 'TESTMODE':
        # Used solely for RDK test to skip actual put_evaluation API call
        testMode = True
    # Invoke the Config API to report the result of the evaluation
    AWS_CONFIG_CLIENT.put_evaluations(Evaluations=evaluations, ResultToken=resultToken, TestMode=testMode)
    # Used solely for RDK test to be able to test Lambda function
    return evaluations

def is_internal_error(exception):
    return ((not isinstance(exception, botocore.exceptions.ClientError)) or exception.response['Error']['Code'].startswith('5')
            or 'InternalError' in exception.response['Error']['Code'] or 'ServiceError' in exception.response['Error']['Code'])

def build_internal_error_response(internalErrorMessage, internalErrorDetails=None):
    return build_error_response(internalErrorMessage, internalErrorDetails, 'InternalError', 'InternalError')

def build_error_response(internalErrorMessage, internalErrorDetails=None, customerErrorCode=None, customerErrorMessage=None):
    error_response = {
        'internalErrorMessage': internalErrorMessage,
        'internalErrorDetails': internalErrorDetails,
        'customerErrorMessage': customerErrorMessage,
        'customerErrorCode': customerErrorCode
    }
    print(error_response)
    return error_response
