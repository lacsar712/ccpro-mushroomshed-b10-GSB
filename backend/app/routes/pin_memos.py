from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.pin_memo import MAX_PINS_PER_ROOM, PinMemo
from app.models.room import Room
from app.models.user import User
from app.schemas.pin_memo import PinMemoCreateSchema, PinMemoOutSchema, PinMemoUpdateSchema
from app.utils import validation_error_response

bp = Blueprint("pin_memos", __name__, url_prefix="/api/pin-memos")

create_schema = PinMemoCreateSchema()
update_schema = PinMemoUpdateSchema()
out_schema = PinMemoOutSchema()
out_many = PinMemoOutSchema(many=True)


def _current_user(db):
    username = get_jwt_identity()
    return db.query(User).filter(User.username == username).first()


def _pinned_count(db, room_id: int) -> int:
    # 计数与写入必须在同一事务：锁定读（InnoDB 间隙锁）防止并发钉入第 4 条
    rows = (
        db.query(PinMemo.id)
        .filter(PinMemo.room_id == room_id, PinMemo.pinned.is_(True))
        .with_for_update()
        .all()
    )
    return len(rows)


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


@bp.get("")
@jwt_required()
def list_pin_memos():
    db = SessionLocal()
    try:
        room_id = request.args.get("roomId", type=int)
        pinned_arg = request.args.get("pinned")
        q = db.query(PinMemo)
        if room_id is not None:
            q = q.filter(PinMemo.room_id == room_id)
        if pinned_arg is not None:
            q = q.filter(PinMemo.pinned.is_(pinned_arg.strip().lower() in ("1", "true")))
        rows = q.order_by(PinMemo.created_at.desc(), PinMemo.id.desc()).all()
        return jsonify(out_many.dump(rows))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_pin_memo():
    db = SessionLocal()
    try:
        user = _current_user(db)
        if not user:
            return jsonify({"detail": "无效或过期的令牌"}), 401
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400

        item = PinMemo(
            room_id=data["room_id"],
            body=data["body"],
            pinned=data["pinned"],
            author_name=user.display_name,
        )
        if item.pinned:
            current_pins = _pinned_count(db, item.room_id)
            if current_pins >= MAX_PINS_PER_ROOM:
                db.rollback()
                return _pin_limit_response(item.room_id, current_pins)
        db.add(item)
        db.commit()
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()


@bp.patch("/<int:memo_id>")
@jwt_required()
def update_pin_memo(memo_id: int):
    db = SessionLocal()
    try:
        user = _current_user(db)
        if not user:
            return jsonify({"detail": "无效或过期的令牌"}), 401
        try:
            data = update_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)

        item = db.query(PinMemo).filter(PinMemo.id == memo_id).first()
        if not item:
            return jsonify({"detail": "置顶备忘不存在"}), 404

        is_admin = user.role == "admin"
        is_author = item.author_name == user.display_name

        if "body" in data and data["body"] != item.body:
            # 作者只能改自己的 body；admin 可改任意 body
            if not (is_admin or is_author):
                return jsonify({"detail": "只能修改本人备忘的内容"}), 403
            item.body = data["body"]

        if "pinned" in data and data["pinned"] != item.pinned:
            if data["pinned"]:
                # 取消置顶后允许再钉，但同室上限仍为 3
                current_pins = _pinned_count(db, item.room_id)
                if current_pins >= MAX_PINS_PER_ROOM:
                    db.rollback()
                    return _pin_limit_response(item.room_id, current_pins)
                item.pinned = True
            else:
                # 拆钉：本人或 admin；fruiter 拆他人的钉 → 403
                if not (is_admin or is_author):
                    return jsonify({"detail": "只能取消本人置顶，或由场长操作"}), 403
                item.pinned = False

        db.commit()
        db.refresh(item)
        return jsonify(out_schema.dump(item))
    finally:
        db.close()
