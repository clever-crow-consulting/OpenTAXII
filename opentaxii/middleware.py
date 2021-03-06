import structlog
from functools import wraps
from flask import Flask, request, make_response

from .taxii.exceptions import (
    raise_failure, StatusMessageException, FailureStatus, UnauthorizedStatus
)
from .taxii.utils import parse_message
from .taxii.status import process_status_exception
from .taxii.bindings import (
    MESSAGE_BINDINGS, SERVICE_BINDINGS, ALL_PROTOCOL_BINDINGS
)
from .taxii.http import (
    get_http_headers, get_content_type, validate_request_headers_post_parse,
    validate_request_headers, validate_response_headers
)
from .utils import extract_token
from .management import management

log = structlog.get_logger(__name__)


def create_app(server):
    app = Flask(__name__)
    app = attach_taxii_server(app, server)

    app.taxii = server

    app.register_error_handler(500, handle_internal_error)
    app.register_error_handler(StatusMessageException, handle_status_exception)

    app.register_blueprint(management, url_prefix='/management')

    return app


def attach_taxii_server(app, server):
    for path, service in server.path_to_service.items():
        app.add_url_rule(
            path,
            service.uid + "_view",
            view_func = service_wrapper(service),
            methods = ['POST']
        )
    return app


def service_wrapper(service):

    @wraps(service.process)
    def wrapper(*args, **kwargs):

        if service.authentication_required:
            token = extract_token(request.headers)
            if not token:
                raise UnauthorizedStatus()
            account = service.server.auth.get_account(token)
            if not account:
                raise UnauthorizedStatus()

        if 'application/xml' not in request.accept_mimetypes:
            raise_failure("The specified values of Accept is not supported: %s" % (request.accept_mimetypes or []))

        validate_request_headers(request.headers, MESSAGE_BINDINGS)

        body = request.data

        taxii_message = parse_message(get_content_type(request.headers), body)
        try:
            validate_request_headers_post_parse(request.headers,
                    supported_message_bindings=MESSAGE_BINDINGS,
                    service_bindings=SERVICE_BINDINGS,
                    protocol_bindings=ALL_PROTOCOL_BINDINGS)
        except StatusMessageException, e:
            e.in_response_to = taxii_message.message_id
            raise e

        response_message = service.process(request.headers, taxii_message)

        response_headers = get_http_headers(response_message.version, request.is_secure)
        validate_response_headers(response_headers)

        # FIXME: pretty-printing should be configurable
        taxii_xml = response_message.to_xml(pretty_print=True)

        return make_taxii_response(taxii_xml, response_headers)

    return wrapper


def make_taxii_response(taxii_xml, taxii_headers):

    validate_response_headers(taxii_headers)
    response = make_response(taxii_xml)

    h = response.headers
    for header, value in taxii_headers.items():
        h[header] = value

    return response


def handle_status_exception(error):
    log.warning('Status exception', exc_info=True)

    if 'application/xml' not in request.accept_mimetypes:
        return 'Unacceptable', 406

    xml, headers = process_status_exception(error, request.headers, request.is_secure)
    return make_taxii_response(xml, headers)


def handle_internal_error(error):
    log.error('Internal error', exc_info=True)

    if 'application/xml' not in request.accept_mimetypes:
        return 'Unacceptable', 406

    new_error = FailureStatus("Error occured", e=error)

    xml, headers = process_status_exception(new_error, request.headers, request.is_secure)
    return make_taxii_response(xml, headers)

