from marshmallow import Schema, fields, pre_load, validate


def _strip_body(data):
    if isinstance(data, dict) and isinstance(data.get("body"), str):
        data = {**data, "body": data["body"].strip()}
    return data


class PinMemoCreateSchema(Schema):
    room_id = fields.Int(required=True, data_key="roomId")
    body = fields.Str(required=True, validate=validate.Length(min=1, max=40))
    pinned = fields.Bool(load_default=True)

    @pre_load
    def strip_body(self, data, **kwargs):
        return _strip_body(data)


class PinMemoUpdateSchema(Schema):
    body = fields.Str(validate=validate.Length(min=1, max=40))
    pinned = fields.Bool()

    @pre_load
    def strip_body(self, data, **kwargs):
        return _strip_body(data)


class PinMemoOutSchema(Schema):
    id = fields.Int(dump_only=True)
    room_id = fields.Int(data_key="roomId")
    body = fields.Str()
    pinned = fields.Bool()
    author_name = fields.Str(data_key="authorName")
    created_at = fields.DateTime(data_key="createdAt")
