import base64
import hashlib


def compute_hash(new_investment):
    string = new_investment['symbol'] + new_investment['investment_account'] + new_investment['purchase_date'] + \
             new_investment['investment_type'] + str(new_investment['purchase_price']) + \
             str(new_investment['position_size'])
    enc_password = string.encode()
    hash_object = hashlib.sha256(enc_password)
    hash_b64 = base64.b64encode(hash_object.digest())
    return hash_b64.decode()
