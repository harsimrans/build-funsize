"""
funsize.database.cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is currently a stub file that contains function prototypes for the
caching layer core

"""

import os
import shutil
import logging
import errno
from StringIO import StringIO
from boto.s3.connection import S3Connection

log = logging.getLogger(__name__)


class CacheBase(object):

    def get_cache_path(self, category, identifier):
        return "files/%s/%s" % (category, identifier)

    def save(self, fp_or_filename, category, identifier, isfilename=False):
        raise NotImplementedError

    def save_blank_file(self, category, identifier):
        raise NotImplementedError

    def is_blank_file(self, category, identifier):
        raise NotImplementedError

    def exists(self, category, identifier):
        raise NotImplementedError

    def retrieve_to_file(self, category, identifier, output_file):
        raise NotImplementedError

    def retrieve_or_redirect(self, category, identifier):
        raise NotImplementedError

    def delete(self, category, identifier):
        raise NotImplementedError


class LocalCache(CacheBase):

    def __init__(self, cache_root):
        self.cache_root = cache_root

    def get_cache_path(self, category, identifier=""):
        # Split the name to avoid file-name-too-long errors
        if identifier:
            identifier = identifier.replace("-", "/")
        return "files/{}/{}".format(category, identifier)

    def abspath(self, category, identifier):
        return os.path.join(
            self.cache_root, self.get_cache_path(category, identifier))

    def mkdir_p(self, directory):
        try:
            os.makedirs(directory, 0700)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    def save(self, fp_or_filename, category, identifier, isfilename=False):
        dest = self.abspath(category, identifier)
        parent_dir = os.path.dirname(dest)
        self.mkdir_p(parent_dir)
        if isfilename:
            shutil.copyfile(fp_or_filename, dest)
        else:
            with open(dest, "wb") as fdest:
                shutil.copyfileobj(fp_or_filename, fdest)

    def save_blank_file(self, category, identifier):
        self.save(StringIO(""), category, identifier)

    def is_blank_file(self, category, identifier):
        dest = self.abspath(category, identifier)
        return os.path.isfile(dest) and os.path.getsize(dest) == 0

    def exists(self, category, identifier):
        dest = self.abspath(category, identifier)
        return os.path.isfile(dest)

    def retrieve_to_file(self, category, identifier, output_file):
        src = self.abspath(category, identifier)
        shutil.copyfile(src, output_file)

    def retrieve_or_redirect(self, category, identifier):
        from flask import send_file
        src = self.abspath(category, identifier)
        return send_file(src, mimetype="application/octet-stream",
                         as_attachment=True)

    def delete(self, category, identifier):
        dest = self.abspath(category, identifier)
        os.remove(dest)


class S3Cache(CacheBase):
    """ Class that provides access to cache
        Assumes all keys are hex-encoded SHA512s
        Internally converts  hex to base64 encoding
    """
    def __init__(self, bucket):
        """ _bucket : bucket name to use for S3 fp_or_filenames """
        # open a connection and get the bucket
        self.conn = S3Connection()
        self.bucket = self.conn.get_bucket(bucket)

    def new_key(self, category, identifier):
        """ Based on identifier and category create a new key in the bucket"""
        key = self.get_cache_path(category, identifier)
        return self.bucket.new_key(key)

    def get_key(self, category, identifier):
        """ Based on identifier and category retrieve key from bucket """
        key = self.get_cache_path(category, identifier)
        return self.bucket.get_key(key)

    def save(self, fp_or_filename, category, identifier, isfilename=False):
        """ Saves given file to cache.
            fp_or_filename can be either a local filepath or a file pointer
            (stream) Returns url of the S3 uploaded fp_or_filename.
        """
        key = self.new_key(category, identifier)
        if isfilename:
            key.set_contents_from_filename(fp_or_filename)
        else:
            key.set_contents_from_file(fp_or_filename)

    def save_blank_file(self, category, identifier):
        """ Method to save a blank file to show a partial has been triggered and
            it is being in progress
        """
        key = self.new_key(category, identifier)
        key.set_contents_from_string('')

    def is_blank_file(self, category, identifier):
        """ Function to check if the file is empty or not. To be used to ensure
            no second triggering is done for the same partial
            Returns True is file exists and is blank, False otherwise
        """
        key = self.get_key(category, identifier)
        if not key:
            return False
        return key.size == 0

    def exists(self, category, identifier):
        """ Checks if file with specified key is in cache
            returns True or False depending on whether the file exists
        """
        return bool(self.get_key(category, identifier))

    def retrieve_to_file(self, category, identifier, output_file):
        key = self.get_key(category, identifier)
        key.get_contents_to_filename(output_file)

    def retrieve_or_redirect(self, category, identifier):
        from flask import redirect
        key = self.get_key(category, identifier)
        expires_in = 60 * 60 * 24 * 2  # 2 days
        url = key.generate_url(expires_in=expires_in)
        return redirect(url)

    def delete(self, category, identifier):
        """ Method to remove a file from cache """
        self.get_key(category, identifier).delete()

if 'FUNSIZE_LOCAL_CACHE_DIR' in os.environ:
    logging.info("Using local cache")
    cache = LocalCache(os.environ["FUNSIZE_LOCAL_CACHE_DIR"])
elif 'FUNSIZE_S3_UPLOAD_BUCKET' in os.environ and \
        'AWS_ACCESS_KEY_ID' in os.environ and\
        'AWS_SECRET_ACCESS_KEY' in os.environ:
    logging.info("Using S3 cache")
    cache = S3Cache(os.environ["FUNSIZE_S3_UPLOAD_BUCKET"])
else:
    logging.info("Default local cache")
    cache = LocalCache("/tmp/funsizecache")
