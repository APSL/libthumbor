#!/usr/bin/python
# -*- coding: utf-8 -*-

# thumbor imaging service
# https://github.com/globocom/thumbor/wiki

# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2011 globo.com timehome@corp.globo.com

import base64
import hashlib
import hmac

from Crypto.Cipher import AES

from .url import Url

from six import text_type, PY3, b, PY2


class Cryptor(object):
    def __init__(self, security_key):
        self.security_key = (security_key * 16)[:16]

    def encrypt(self,
                width,
                height,
                smart,
                adaptive,
                full,
                fit_in,
                flip_horizontal,
                flip_vertical,
                halign,
                valign,
                trim,
                crop_left,
                crop_top,
                crop_right,
                crop_bottom,
                filters,
                image):

        generated_url = Url.generate_options(
            width=width,
            height=height,
            smart=smart,
            meta=False,
            adaptive=adaptive,
            full=full,
            fit_in=fit_in,
            horizontal_flip=flip_horizontal,
            vertical_flip=flip_vertical,
            halign=halign,
            valign=valign,
            trim=trim,
            crop_left=crop_left,
            crop_top=crop_top,
            crop_right=crop_right,
            crop_bottom=crop_bottom,
            filters=filters
        )

        url = "%s/%s" % (generated_url, hashlib.md5(b(image)).hexdigest())

        pad = lambda s: s + (16 - len(s) % 16) * "{"
        cipher = AES.new(self.security_key)
        if PY2:
            url = url.encode('utf-8')
        encrypted = base64.urlsafe_b64encode(cipher.encrypt(pad(url)))

        return encrypted

    def get_options(self, encrypted_url_part, image_url):
        try:
            opt = self.decrypt(encrypted_url_part)
        except ValueError:
            opt = None

        if not opt and not self.security_key and self.context.config.STORES_CRYPTO_KEY_FOR_EACH_IMAGE:
            security_key = self.storage.get_crypto(image_url)

            if security_key is not None:
                cr = Cryptor(security_key)
                try:
                    opt = cr.decrypt(encrypted_url_part)
                except ValueError:
                    opt = None

        if opt is None:
            return None

        image_hash = opt and opt.get('image_hash')
        image_hash = image_hash[1:] if image_hash and image_hash.startswith('/') else image_hash

        path_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()

        if not image_hash or image_hash != path_hash:
            return None

        opt['image'] = image_url
        opt['hash'] = opt['image_hash']
        del opt['image_hash']

        return opt

    def decrypt(self, encrypted):
        cipher = AES.new(self.security_key)

        try:
            debased = base64.urlsafe_b64decode(encrypted.encode("utf-8"))
            decrypted = cipher.decrypt(debased)
            if PY3:
                decrypted = decrypted.decode('ascii')
            decrypted = decrypted.rstrip('{')
        except TypeError:
            return None

        result = Url.parse_decrypted('/%s' % decrypted)

        result['image_hash'] = result['image']
        del result['image']

        return result


class Signer:
    def __init__(self, security_key):
        if isinstance(security_key, text_type):
            security_key = security_key.encode('utf-8')
        self.security_key = security_key

    def validate(self, actual_signature, url):
        url_signature = self.signature(url)
        return url_signature == actual_signature

    def signature(self, url):
        return base64.urlsafe_b64encode(hmac.new(self.security_key, text_type(url).encode('utf-8'), hashlib.sha1).digest())
