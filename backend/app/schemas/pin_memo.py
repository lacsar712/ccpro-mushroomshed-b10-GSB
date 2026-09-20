from marshmallow import Schema, fields, pre_load, validate

BODY_LENGTH = validate.Length(min=1, max=40, error="body 去空白后须为 1–40 字")


class _TrimBodyMixin:
    @pre_load
    def trim_body(self, data, **kwargs):
        if isinstance(data, dict) and isinstance(data.get("body"), str):
            data = {**data, "body": data["body"].strip()}
        return data


class PinMemoCreateSchema(_TrimBodyMixin, Schema):
    room_id = fields.Int(required=True, data_key="roomId")
    body = fields.Str(required=True, validate=BODY_LENGTH)
    pinned = fields.Bool(load_default=True)


class PinMemoUpdateSchema(_TrimBodyMixin, Schema):
    body = fields.Str(validate=BODY_LENGTH)
    pinned = fields.Bool()


class PinMemoOutSchema(Schema):
    id = fields.Int(dump_only=True)
    room_id = fields.Int(data_key="roomId")
    body = fields.Str()
    pinned = fields.Bool()
    author_name = fields.Str(data_key="authorName")
    created_at = fields.DateTime(data_key="createdAt")
