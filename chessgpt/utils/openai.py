import hashlib


def get_conversation_id_hash(conversation_id):
    return hashlib.md5(conversation_id.encode("utf-8")).hexdigest()
