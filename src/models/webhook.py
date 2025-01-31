from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewsletterContentType(int, Enum):
    """Content type for forwarded newsletter messages"""

    UPDATE = 1
    UPDATE_CARD = 2
    LINK_CARD = 3


class ListMessageType(int, Enum):
    """Type of list message"""

    UNKNOWN = 0
    SINGLE_SELECT = 1
    PRODUCT_LIST = 2


class MessageKey(BaseModel):
    """Key identifying a message"""

    remote_jid: Optional[str] = Field(None, alias="remoteJID")
    from_me: Optional[bool] = Field(None, alias="fromMe")
    id: Optional[str] = Field(None, alias="ID")
    participant: Optional[str] = None


class Message(BaseModel):
    """Basic message structure"""

    id: Optional[str] = None
    text: Optional[str] = None
    replied_id: Optional[str] = Field(None, alias="replied_id")
    quoted_message: Optional[str] = Field(None, alias="quoted_message")


class Reaction(BaseModel):
    """Reaction message structure"""

    id: Optional[str] = None
    message: Optional[str] = None


class ExtractedMedia(BaseModel):
    """Structure for downloaded media content"""

    media_path: str = Field(..., alias="media_path")
    mime_type: str = Field(..., alias="mime_type")
    caption: str


class ForwardedNewsletterMessageInfo(BaseModel):
    """Information about a forwarded newsletter message"""

    newsletter_jid: Optional[str] = Field(None, alias="newsletterJID")
    server_message_id: Optional[int] = Field(None, alias="serverMessageID")
    newsletter_name: Optional[str] = Field(None, alias="newsletterName")
    content_type: Optional[NewsletterContentType] = Field(None, alias="contentType")
    accessibility_text: Optional[str] = Field(None, alias="accessibilityText")


class ContextInfo(BaseModel):
    """Context information for WhatsApp messages"""

    stanza_id: Optional[str] = Field(None, alias="stanzaID")
    participant: Optional[str] = None
    quoted_message: Optional[Message] = Field(None, alias="quotedMessage")
    remote_jid: Optional[str] = Field(None, alias="remoteJID")
    mentioned_jid: Optional[List[str]] = Field(None, alias="mentionedJID")
    conversion_source: Optional[str] = Field(None, alias="conversionSource")
    conversion_data: Optional[bytes] = Field(None, alias="conversionData")
    conversion_delay_seconds: Optional[int] = Field(
        None, alias="conversionDelaySeconds"
    )
    forwarding_score: Optional[int] = Field(None, alias="forwardingScore")
    is_forwarded: Optional[bool] = Field(None, alias="isForwarded")
    quoted_ad: Optional[Any] = Field(None, alias="quotedAd")
    placeholder_key: Optional[MessageKey] = Field(None, alias="placeholderKey")
    expiration: Optional[int] = None
    ephemeral_setting_timestamp: Optional[int] = Field(
        None, alias="ephemeralSettingTimestamp"
    )
    ephemeral_shared_secret: Optional[bytes] = Field(
        None, alias="ephemeralSharedSecret"
    )
    external_ad_reply: Optional[Any] = Field(None, alias="externalAdReply")
    entry_point_conversion_source: Optional[str] = Field(
        None, alias="entryPointConversionSource"
    )
    entry_point_conversion_app: Optional[str] = Field(
        None, alias="entryPointConversionApp"
    )
    entry_point_conversion_delay_seconds: Optional[int] = Field(
        None, alias="entryPointConversionDelaySeconds"
    )
    disappearing_mode: Optional[Any] = Field(None, alias="disappearingMode")
    action_link: Optional[Any] = Field(None, alias="actionLink")
    group_subject: Optional[str] = Field(None, alias="groupSubject")
    parent_group_jid: Optional[str] = Field(None, alias="parentGroupJID")
    trust_banner_type: Optional[str] = Field(None, alias="trustBannerType")
    trust_banner_action: Optional[int] = Field(None, alias="trustBannerAction")
    is_sampled: Optional[bool] = Field(None, alias="isSampled")
    group_mentions: Optional[List[Any]] = Field(None, alias="groupMentions")
    utm: Optional[Any] = Field(None, alias="utm")
    forwarded_newsletter_message_info: Optional[ForwardedNewsletterMessageInfo] = Field(
        None, alias="forwardedNewsletterMessageInfo"
    )
    business_message_forward_info: Optional[Any] = Field(
        None, alias="businessMessageForwardInfo"
    )
    smb_client_campaign_id: Optional[str] = Field(None, alias="smbClientCampaignID")
    smb_server_campaign_id: Optional[str] = Field(None, alias="smbServerCampaignID")
    data_sharing_context: Optional[Any] = Field(None, alias="dataSharingContext")
    always_show_ad_attribution: Optional[bool] = Field(
        None, alias="alwaysShowAdAttribution"
    )
    feature_eligibilities: Optional[Any] = Field(None, alias="featureEligibilities")
    entry_point_conversion_external_source: Optional[str] = Field(
        None, alias="entryPointConversionExternalSource"
    )
    entry_point_conversion_external_medium: Optional[str] = Field(
        None, alias="entryPointConversionExternalMedium"
    )
    ctwa_signals: Optional[str] = Field(None, alias="ctwaSignals")
    ctwa_payload: Optional[bytes] = Field(None, alias="ctwaPayload")
    forwarded_ai_bot_message_info: Optional[Any] = Field(
        None, alias="forwardedAiBotMessageInfo"
    )
    status_attribution_type: Optional[Any] = Field(None, alias="statusAttributionType")
    url_tracking_map: Optional[Any] = Field(None, alias="urlTrackingMap")


class ListMessageRow(BaseModel):
    """Row in a ListMessage section"""

    title: Optional[str] = None
    description: Optional[str] = None
    row_id: Optional[str] = Field(None, alias="rowID")


class ListMessageProduct(BaseModel):
    """Product in a ListMessage product section"""

    product_id: Optional[str] = Field(None, alias="productID")


class ProductListHeaderImage(BaseModel):
    """Header image for a product list"""

    product_id: Optional[str] = Field(None, alias="productID")
    jpeg_thumbnail: Optional[bytes] = Field(None, alias="JPEGThumbnail")


class ListMessageSection(BaseModel):
    """Section in a ListMessage"""

    title: Optional[str] = None
    rows: Optional[List[ListMessageRow]] = None


class ProductSection(BaseModel):
    """Product section in a ListMessage"""

    title: Optional[str] = None
    products: Optional[List[ListMessageProduct]] = None


class ProductListInfo(BaseModel):
    """Product list information for a ListMessage"""

    product_sections: Optional[List[ProductSection]] = Field(
        None, alias="productSections"
    )
    header_image: Optional[ProductListHeaderImage] = Field(None, alias="headerImage")
    business_owner_jid: Optional[str] = Field(None, alias="businessOwnerJID")


class ListMessage(BaseModel):
    """WhatsApp list message structure"""

    title: Optional[str] = None
    description: Optional[str] = None
    button_text: Optional[str] = Field(None, alias="buttonText")
    list_type: Optional[ListMessageType] = Field(None, alias="listType")
    sections: Optional[List[ListMessageSection]] = None
    product_list_info: Optional[ProductListInfo] = Field(None, alias="productListInfo")
    footer_text: Optional[str] = Field(None, alias="footerText")
    context_info: Optional[ContextInfo] = Field(None, alias="contextInfo")


class OrderMessage(BaseModel):
    """WhatsApp order message structure"""

    order_id: Optional[str] = Field(None, alias="orderID")
    thumbnail: Optional[bytes] = None
    item_count: Optional[int] = Field(None, alias="itemCount")
    status: Optional[str] = None
    surface: Optional[str] = None
    message: Optional[str] = None
    order_title: Optional[str] = Field(None, alias="orderTitle")
    seller_jid: Optional[str] = Field(None, alias="sellerJID")
    token: Optional[str] = None
    total_amount_1000: Optional[int] = Field(None, alias="totalAmount1000")
    total_currency_code: Optional[str] = Field(None, alias="totalCurrencyCode")
    context_info: Optional[ContextInfo] = Field(None, alias="contextInfo")
    message_version: Optional[int] = Field(None, alias="messageVersion")
    order_request_message_id: Optional[MessageKey] = Field(
        None, alias="orderRequestMessageID"
    )


class LocationMessage(BaseModel):
    """WhatsApp location message structure"""

    degrees_latitude: Optional[float] = Field(None, alias="degreesLatitude")
    degrees_longitude: Optional[float] = Field(None, alias="degreesLongitude")
    name: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = Field(None, alias="URL")
    is_live: Optional[bool] = Field(None, alias="isLive")
    accuracy_in_meters: Optional[int] = Field(None, alias="accuracyInMeters")
    speed_in_mps: Optional[float] = Field(None, alias="speedInMps")
    degrees_clockwise_from_magnetic_north: Optional[int] = Field(
        None, alias="degreesClockwiseFromMagneticNorth"
    )
    comment: Optional[str] = None
    jpeg_thumbnail: Optional[bytes] = Field(None, alias="JPEGThumbnail")
    context_info: Optional[ContextInfo] = Field(None, alias="contextInfo")


class ContactMessage(BaseModel):
    """WhatsApp contact message structure"""

    display_name: Optional[str] = Field(None, alias="displayName")
    vcard: Optional[str] = None
    context_info: Optional[ContextInfo] = Field(None, alias="contextInfo")


class WhatsAppWebhookPayload(BaseModel):
    """
    Pydantic model representing the WhatsApp webhook payload structure.
    This model represents the actual JSON structure that is sent to the webhook
    after media has been extracted and downloaded.
    """

    # Basic info
    from_: Optional[str] = Field(
        None, alias="from", description="Source of the message"
    )
    timestamp: datetime = Field(..., description="Message timestamp in RFC3339 format")
    pushname: Optional[str] = Field(None, description="Push name of the sender")

    # Message content
    message: Optional[Message] = Field(
        None, description="Text message content and metadata"
    )
    reaction: Optional[Reaction] = Field(None, description="Message reaction content")

    # Media content
    audio: Optional[ExtractedMedia] = Field(
        None, description="Extracted audio file info"
    )
    document: Optional[ExtractedMedia] = Field(
        None, description="Extracted document file info"
    )
    image: Optional[ExtractedMedia] = Field(
        None, description="Extracted image file info"
    )
    sticker: Optional[ExtractedMedia] = Field(
        None, description="Extracted sticker file info"
    )
    video: Optional[ExtractedMedia] = Field(
        None, description="Extracted video file info"
    )

    # Special message types
    contact: Optional[ContactMessage] = Field(
        None, description="Contact message content"
    )
    list: Optional[ListMessage] = Field(None, description="List message content")
    location: Optional[LocationMessage] = Field(
        None, description="Location message content"
    )
    order: Optional[OrderMessage] = Field(None, description="Order message content")

    # Flags
    view_once: Optional[bool] = Field(
        False, description="Whether the message is view once"
    )
    forwarded: Optional[bool] = Field(
        False, description="Whether the message is forwarded"
    )

    @field_validator("timestamp")
    def validate_timestamp(cls, v):
        """Ensure timestamp is in RFC3339 format"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as err:
                raise ValueError("timestamp must be in RFC3339 format") from err
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "from": "1234567890@s.whatsapp.net",
                "timestamp": "2024-01-29T12:00:00Z",
                "pushname": "John Doe",
                "message": {"id": "123456", "text": "Hello, world!"},
                "document": {
                    "media_path": "/path/to/file.pdf",
                    "mime_type": "application/pdf",
                    "caption": "Important document",
                },
                "location": {
                    "degreesLatitude": 37.7749,
                    "degreesLongitude": -122.4194,
                    "name": "San Francisco",
                    "address": "California, USA",
                },
            }
        },
    )
