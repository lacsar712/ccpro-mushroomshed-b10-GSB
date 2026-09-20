from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.pin_memo import PinMemo
from app.models.room import Room
from app.models.user import User
from app.schemas.pin_memo import PinMemoCreateSchema, PinMemoOutSchema, PinMemoUpdateSchema
from app.utils import validation_error_response

bp = Blueprint("pin_memos", __name__, url_prefix="/api/pin-memos")

MAX_PINS_PER_ROOM = 3

create_schema = PinMemoCreateSchema()
update_schema = PinMemoUpdateSchema()
out_schema = PinMemoOutSchema()
out_many = PinMemoOutSchema(many=True)


def _current_user(db) -> User | None:
    username = get_jwt_identity()
    return db.query(User).filter(User.username == username).first()


def _pinned_count(db, room_id: int) -> int:
    return (
        db.query(PinMemo)
        .filter(PinMemo.room_id == room_id, PinMemo.pinned.is_(True))
        .count()
    )


def _pin_limit_response(room_id: int, current_pins: int):
    return (
        jsonify(
            {
                "detail": f"同室置顶备忘最多 {MAX_PINS_PER_ROOM} 条",
                "roomId": room_id,
                "currentPins": current_pins,
            }
        ),
        409,
    )


def _parse_pinned_arg():
    raw = request.args.get("pinned")
    if raw is None:
        return None
    if raw in ("1", "true", "True"):
        return True
    if raw in ("0", "false", "False"):
        return False
    return "invalid"


@bp.get("")
@jwt_required()
def list_pin_memos():
    db = SessionLocal()
    try:
        q = db.query(PinMemo)
        room_id = request.args.get("roomId", type=int)
        if room_id is not None:
            q = q.filter(PinMemo.room_id == room_id)
        pinned = _parse_pinned_arg()
        if pinned == "invalid":
            return jsonify({"detail": "pinned 仅接受 0/1"}), 400
        if pinned is not None:
            q = q.filter(PinMemo.pinned.is_(pinned))
        rows = q.order_by(PinMemo.created_at.desc(), PinMemo.id.desc()).all()
        return jsonify(out_many.dump(rows))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_pin_memo():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        user = _current_user(db)
        if not user:
            return jsonify({"detail": "无效或过期的令牌"}), 401
        # 锁住室行：计数与写入保持在同一事务内，并发钉也不会超限
        room = db.query(Room).filter(Room.id == data["room_id"]).with_for_update().first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400
        if data["pinned"]:
            current_pins = _pinned_count(db, room.id)
            if current_pins >= MAX_PINS_PER_ROOM:
                db.rollback()
                return _pin_limit_response(room.id, current_pins)
        item = PinMemo(
            room_id=room.id,
            body=data["body"],
            pinned=data["pinned"],
            author_name=user.display_name,
        )
        db.add(item)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            return jsonify({"detail": "写入失败，已回滚"}), 500
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()


@bp.patch("/<int:memo_id>")
@jwt_required()
def update_pin_memo(memo_id: int):
    db = SessionLocal()
    try:
        try:
            data = update_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        if not data:
            return jsonify({"detail": "无有效更新字段"}), 400
        user = _current_user(db)
        if not user:
            return jsonify({"detail": "无效或过期的令牌"}), 401
        item = db.query(PinMemo).filter(PinMemo.id == memo_id).first()
        if not item:
            return jsonify({"detail": "置顶备忘不存在"}), 404
        is_admin = user.role == "admin"
        is_author = item.author_name == user.display_name

        if "body" in data and not (is_admin or is_author):
            return jsonify({"detail": "只能修改本人备忘正文"}), 403

        if "pinned" in data and data["pinned"] != item.pinned:
            if not (is_admin or is_author):
                return jsonify({"detail": "无权拆除他人置顶备忘"}), 403
            if data["pinned"]:
                # 取消后可再钉；再钉同样占用名额，计数与写入同事务
                db.query(Room).filter(Room.id == item.room_id).with_for_update().first()
                current_pins = _pinned_count(db, item.room_id)
                if current_pins >= MAX_PINS_PER_ROOM:
                    db.rollback()
                    return _pin_limit_response(item.room_id, current_pins)
            item.pinned = data["pinned"]

        if "body" in data:
            item.body = data["body"]
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            return jsonify({"detail": "写入失败，已回滚"}), 500
        db.refresh(item)
        return jsonify(out_schema.dump(item))
    finally:
        db.close()
