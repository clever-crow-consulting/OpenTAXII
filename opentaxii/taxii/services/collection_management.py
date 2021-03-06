from libtaxii.constants import (
        SVC_COLLECTION_MANAGEMENT,
        MSG_COLLECTION_INFORMATION_REQUEST, MSG_FEED_INFORMATION_REQUEST,
        MSG_MANAGE_COLLECTION_SUBSCRIPTION_REQUEST,
        MSG_MANAGE_FEED_SUBSCRIPTION_REQUEST,
)

from .abstract import TaxiiService
from .handlers import (
        CollectionInformationRequestHandler,
        SubscriptionRequestHandler
)


class CollectionManagementService(TaxiiService):

    handlers = {
        MSG_COLLECTION_INFORMATION_REQUEST : CollectionInformationRequestHandler,
        MSG_FEED_INFORMATION_REQUEST : CollectionInformationRequestHandler,

    }

    subscription_handlers = {
        MSG_MANAGE_COLLECTION_SUBSCRIPTION_REQUEST : SubscriptionRequestHandler,
        MSG_MANAGE_FEED_SUBSCRIPTION_REQUEST : SubscriptionRequestHandler
    }
            
    service_type = SVC_COLLECTION_MANAGEMENT

    subscription_message = "Default subscription message"
    subscriptions_supported = True

    def __init__(self, subscriptions_supported=True, subscription_message=None, **kwargs):
        super(CollectionManagementService, self).__init__(**kwargs)

        self.subscription_message = subscription_message
        self.subscriptions_supported = subscriptions_supported

        if self.subscriptions_supported:
            self.handlers = dict(CollectionManagementService.handlers)
            self.handlers.update(CollectionManagementService.subscription_handlers)


    @property
    def advertised_collections(self):
        return self.server.persistence.get_collections(service_id=self.id)


    def get_collection(self, name):
        return self.server.persistence.get_collection(name, self.id)


    def get_push_methods(self, collection):
        # Push delivery is not implemented
        pass


    def get_polling_services(self, collection):
        return self.server.get_services_for_collection(collection, 'poll')

    def get_subscription_services(self, collection):
        services = []
        all_services = self.server.get_services_for_collection(collection,
                'collection_management')
        for s in all_services:
            if s.subscriptions_supported:
                services.append(s)
        return services

    def create_subscription(self, subscription):
        subscription.subscription_id = self.generate_id()
        return self.server.persistence.create_subscription(subscription,
                service_id=self.id)

    def get_subscription(self, subscription_id):
        return self.server.persistence.get_subscription(subscription_id)

    def get_subscriptions(self):
        return self.server.persistence.get_subscriptions(service_id=self.id)

    def update_subscription(self, subscription, new_status):
        return self.server.persistence.update_subscription(subscription, new_status)

    def get_receiving_inbox_services(self, collection):
        return self.server.get_services_for_collection(collection, 'inbox')

    def get_volume(self, collection):
        return self.server.persistence.get_content_blocks_count(collection.id)


