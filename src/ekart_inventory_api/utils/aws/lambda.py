import json
from enum import Enum
from typing import Any, Dict

from fastapi import HTTPException


class InvocationType(str, Enum):
    REQUEST_RESPONSE = "RequestResponse"
    EVENT = "Event"


class LambdaException(Exception):
    def __init__(
        self, status_code: int = None, function_error: str = None, message: str = ""
    ):
        self.status_code = status_code
        self.function_error = function_error
        self.message = message or "An error occurred in Lambda execution."
        super().__init__(self.message)


async def invoke_lambda_async(
    lambda_client,
    function_name: str,
    payload: Dict[str, Any],
    invocation_type: InvocationType = InvocationType.REQUEST_RESPONSE.value,
) -> Dict[str, Any]:
    """
    Asynchronously invokes an AWS Lambda function.

    :param lambda_client: The aiobotocore Lambda client.
    :param function_name: Name of the Lambda function.
    :param payload: Payload to send to the Lambda function (should be a dict).
    :param invocation_type: Type of invocation, either 'RequestResponse' or 'Event'. Default is 'RequestResponse'.
    :return: Response from the Lambda function.
    :raises HTTPException: If Lambda invocation fails.
    """
    if (
        not hasattr(lambda_client, "_service_model")
        or lambda_client._service_model.service_name != "lambda"
    ):
        raise ValueError("Provided client is not a Lambda client.")

    try:
        # Convert payload to JSON
        payload_json = json.dumps(payload).encode("utf-8")

        # Ensure invocation type is valid
        if invocation_type not in InvocationType:
            raise ValueError(f"Invalid invocation type: {invocation_type}")

        # Invoke Lambda function asynchronously
        response = await lambda_client.invoke(
            FunctionName=function_name,
            Payload=payload_json,
            InvocationType=invocation_type,
        )
        # Read and process response payload
        response_payload = await response["Payload"].read()
        response_data = json.loads(response_payload.decode("utf-8"))

        return _handle_lambda_response(response_data, invocation_type)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invoke Lambda function {function_name}: {str(e)}",
        )


def _handle_lambda_response(
    response: Dict[str, Any], invocation_type: InvocationType
) -> Dict[str, Any]:
    """
    Handles the response from AWS Lambda based on the invocation type.

    :param response: The response object from AWS Lambda.
    :param invocation_type: The invocation type (either RequestResponse or Event).
    :return: Parsed response payload or empty dictionary for Event type.
    :raises LambdaException: If the response status code is not as expected.
    """
    status_code = response.get("statusCode", None)
    function_error = response.get("FunctionError", "")

    if invocation_type == InvocationType.REQUEST_RESPONSE:
        if status_code in (200, 204):
            return response
        raise LambdaException(
            status_code, function_error, "RequestResponse invocation failed."
        )

    elif invocation_type == InvocationType.EVENT:
        if status_code == 202:
            return {}
        raise LambdaException(status_code, function_error, "Event invocation failed.")
