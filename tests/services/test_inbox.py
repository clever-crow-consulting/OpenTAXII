import pytest

from libtaxii import messages_10 as tm10
from libtaxii import messages_11 as tm11

from opentaxii.taxii import exceptions
from opentaxii.utils import create_services_from_object, get_config_for_tests
from opentaxii.server import create_server

from utils import get_service, prepare_headers, as_tm
from fixtures import *


def make_content(version, content_binding=CUSTOM_CONTENT_BINDING, content=CONTENT, subtype=None):
    if version == 10:
        return tm10.ContentBlock(content_binding, content)

    elif version == 11:
        content_block = tm11.ContentBlock(tm11.ContentBinding(content_binding), content)
        if subtype:
            content_block.content_binding.subtype_ids.append(subtype)

        return content_block
    else:
        raise ValueError('Unknown TAXII message version: %s' % version)



def make_inbox_message(version, blocks=None, dest_collection=None):

    if version == 10:
        inbox_message = tm10.InboxMessage(message_id=MESSAGE_ID, content_blocks=blocks)

    elif version == 11:
        inbox_message = tm11.InboxMessage(message_id=MESSAGE_ID, content_blocks=blocks)
        if dest_collection:
            inbox_message.destination_collection_names.append(dest_collection)
    else:
        raise ValueError('Unknown TAXII message version: %s' % version)

    return inbox_message

@pytest.fixture
def server():

    config = get_config_for_tests(DOMAIN)
    server = create_server(config)

    create_services_from_object(SERVICES, server.persistence)
    server.reload_services()

    coll_mapping = {
        'inbox-A' : COLLECTIONS_A,
        'inbox-B' : COLLECTIONS_B
    }
    for service, collections in coll_mapping.items():
        for coll in collections:
            coll = server.persistence.create_collection(coll)
            server.persistence.attach_collection_to_services(coll.id,
                    services_ids=[service])
    
    return server



@pytest.mark.parametrize("https", [True, False])
@pytest.mark.parametrize("version", [11, 10])
def test_inbox_request_all_content(server, version, https):

    inbox_a = get_service(server, 'inbox-A')

    headers = prepare_headers(version, https)

    blocks = [
        make_content(version, content_binding=CUSTOM_CONTENT_BINDING, subtype=CONTENT_BINDING_SUBTYPE),
        make_content(version, content_binding=INVALID_CONTENT_BINDING)
    ]
    inbox_message = make_inbox_message(version, blocks=blocks)

    # "inbox-A" accepts all content
    response = inbox_a.process(headers, inbox_message)

    assert isinstance(response, as_tm(version).StatusMessage)

    assert response.status_type == ST_SUCCESS
    assert response.in_response_to == MESSAGE_ID

    blocks = server.persistence.get_content_blocks(None)
    assert len(blocks) == len(blocks)


@pytest.mark.parametrize("https", [True, False])
def test_inbox_request_destination_collection(server, https):
    version = 11

    inbox_message = make_inbox_message(version, blocks=[make_content(version)], dest_collection=None)
    headers = prepare_headers(version, https)

    inbox = get_service(server, 'inbox-A')
    # destination collection is not required for inbox-A
    response = inbox.process(headers, inbox_message)

    assert isinstance(response, as_tm(version).StatusMessage)
    assert response.status_type == ST_SUCCESS

    inbox = get_service(server, 'inbox-B')
    # destination collection is required for inbox-B
    with pytest.raises(exceptions.StatusMessageException):
        response = inbox.process(headers, inbox_message)


@pytest.mark.parametrize("https", [True, False])
@pytest.mark.parametrize("version", [11, 10])
def test_inbox_request_inbox_valid_content_binding(server, version, https):

    inbox = get_service(server, 'inbox-B')

    blocks = [
        make_content(version, content_binding=CUSTOM_CONTENT_BINDING, subtype=CONTENT_BINDING_SUBTYPE),
        make_content(version, content_binding=CB_STIX_XML_111)
    ]

    inbox_message = make_inbox_message(version, dest_collection=COLLECTION_OPEN, blocks=blocks)
    headers = prepare_headers(version, https)

    response = inbox.process(headers, inbox_message)

    assert isinstance(response, as_tm(version).StatusMessage)
    assert response.status_type == ST_SUCCESS
    assert response.in_response_to == MESSAGE_ID

    blocks = server.persistence.get_content_blocks(collection_id=None) # all blocks
    assert len(blocks) == len(blocks)


@pytest.mark.parametrize("https", [True, False])
@pytest.mark.parametrize("version", [11, 10])
def test_inbox_request_inbox_invalid_inbox_content_binding(server, version, https):

    inbox = get_service(server, 'inbox-B')

    content = make_content(version, content_binding=INVALID_CONTENT_BINDING)
    inbox_message = make_inbox_message(version, dest_collection=COLLECTION_OPEN, blocks=[content])

    headers = prepare_headers(version, https)

    response = inbox.process(headers, inbox_message)

    assert isinstance(response, as_tm(version).StatusMessage)
    assert response.status_type == ST_SUCCESS
    assert response.in_response_to == MESSAGE_ID

    blocks = server.persistence.get_content_blocks(None)

    # Content blocks with invalid content should be ignored
    assert len(blocks) == 0


@pytest.mark.parametrize("https", [True, False])
@pytest.mark.parametrize("version", [11, 10])
def test_inbox_request_collection_content_bindings_filtering(server, version, https):

    inbox = get_service(server, 'inbox-B')
    headers = prepare_headers(version, https)

    blocks = [
        make_content(version, content_binding=CUSTOM_CONTENT_BINDING),
        make_content(version, content_binding=INVALID_CONTENT_BINDING),
    ]

    inbox_message = make_inbox_message(version, dest_collection=COLLECTION_ONLY_STIX, blocks=blocks)

    response = inbox.process(headers, inbox_message)

    assert isinstance(response, as_tm(version).StatusMessage)
    assert response.status_type == ST_SUCCESS
    assert response.in_response_to == MESSAGE_ID

    blocks = server.persistence.get_content_blocks(None)

    # Content blocks with invalid content should be ignored
    assert len(blocks) == 1


