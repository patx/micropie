#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KenobiDB is a small document-based DB, supporting simple usage including
insertion, removal, and basic search.
Written by Harrison Erd (https://patx.github.io/)
https://patx.github.io/kenobi/
"""
# Copyright Harrison Erd
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import json
import sqlite3
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
import re

class KenobiDB:
    """
    A lightweight document-based database built on SQLite. Supports basic
    operations such as insert, remove, search, update, and asynchronous
    execution.
    """

    def __init__(self, file):
        """
        Initialize the KenobiDB instance.

        Args:
            file (str): Path to the SQLite file. If it does not exist,
                it will be created.
        """
        self.file = os.path.expanduser(file)
        self._lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._regexp_connections = set()  # Track connections with REGEXP added
        self._connection = sqlite3.connect(self.file, check_same_thread=False)
        self._add_regexp_support(self._connection)  # Add REGEXP support lazily
        self._initialize_db()

    def _initialize_db(self):
        """
        Create the table and index if they do not exist, and set
        journal mode to WAL.
        """
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_key
                ON documents (
                    json_extract(data, '$.key')
                )
            """)
            self._connection.execute("PRAGMA journal_mode=WAL;")

    @staticmethod
    def _add_regexp_support(conn):
        """
        Add REGEXP function support to the SQLite connection.
        """
        def regexp(pattern, value):
            return re.search(pattern, value) is not None
        conn.create_function("REGEXP", 2, regexp)

    def _get_connection(self):
        """
        Return the active SQLite connection.
        """
        return self._connection

    def insert(self, document):
        """
        Insert a single document (dict) into the database.

        Args:
            document (dict): The document to insert.

        Returns:
            bool: True upon successful insertion.

        Raises:
            TypeError: If the provided document is not a dictionary.
        """
        if not isinstance(document, dict):
            raise TypeError("Must insert a dict")
        with self._lock:
            self._connection.execute(
                "INSERT INTO documents (data) VALUES (?)",
                (json.dumps(document),)
            )
            self._connection.commit()
            return True

    def insert_many(self, document_list):
        """
        Insert multiple documents (list of dicts) into the database.

        Args:
            document_list (list): The list of documents to insert.

        Returns:
            bool: True upon successful insertion.

        Raises:
            TypeError: If the provided object is not a list of dicts.
        """
        if (
            not isinstance(document_list, list)
            or not all(isinstance(doc, dict) for doc in document_list)
        ):
            raise TypeError("Must insert a list of dicts")
        with self._lock:
            self._connection.executemany(
                "INSERT INTO documents (data) VALUES (?)",
                [(json.dumps(doc),) for doc in document_list]
            )
            self._connection.commit()
            return True

    def remove(self, key, value):
        """
        Remove all documents where the given key matches the specified value.

        Args:
            key (str): The field name to match.
            value (Any): The value to match.

        Returns:
            int: Number of documents removed.

        Raises:
            ValueError: If 'key' is empty or 'value' is None.
        """
        if not key or not isinstance(key, str):
            raise ValueError("key must be a non-empty string")
        if value is None:
            raise ValueError("value cannot be None")
        query = (
            "DELETE FROM documents "
            "WHERE json_extract(data, '$.' || ?) = ?"
        )
        with self._lock:
            result = self._connection.execute(query, (key, value))
            self._connection.commit()
            return result.rowcount

    def update(self, id_key, id_value, new_dict):
        """
        Update documents that match (id_key == id_value) by merging new_dict.

        Args:
            id_key (str): The field name to match.
            id_value (Any): The value to match.
            new_dict (dict): A dictionary of changes to apply.

        Returns:
            bool: True if at least one document was updated, False otherwise.

        Raises:
            TypeError: If new_dict is not a dict.
            ValueError: If id_key is invalid or id_value is None.
        """
        if not isinstance(new_dict, dict):
            raise TypeError("new_dict must be a dictionary")
        if not id_key or not isinstance(id_key, str):
            raise ValueError("id_key must be a non-empty string")
        if id_value is None:
            raise ValueError("id_value cannot be None")

        select_query = (
            "SELECT data FROM documents "
            "WHERE json_extract(data, '$.' || ?) = ?"
        )
        update_query = (
            "UPDATE documents "
            "SET data = ? "
            "WHERE json_extract(data, '$.' || ?) = ?"
        )
        with self._lock:
            cursor = self._connection.execute(select_query, (id_key, id_value))
            documents = cursor.fetchall()
            if not documents:
                return False
            for row in documents:
                document = json.loads(row[0])
                if not isinstance(document, dict):
                    continue
                document.update(new_dict)
                self._connection.execute(
                    update_query,
                    (json.dumps(document), id_key, id_value)
                )
            self._connection.commit()
            return True

    def purge(self):
        """
        Remove all documents from the database.

        Returns:
            bool: True upon successful purge.
        """
        with self._lock:
            self._connection.execute("DELETE FROM documents")
            self._connection.commit()
            return True

    def all(self, limit=100, offset=0):
        """
        Return a paginated list of all documents.

        Args:
            limit (int): The maximum number of documents to return.
            offset (int): The starting point for retrieval.

        Returns:
            list: A list of all documents (dicts).
        """
        query = "SELECT data FROM documents LIMIT ? OFFSET ?"
        with self._lock:
            cursor = self._connection.execute(query, (limit, offset))
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def search(self, key, value, limit=100, offset=0):
        """
        Return a list of documents matching (key == value).

        Args:
            key (str): The document field to match on.
            value (Any): The value for which to search.
            limit (int): The maximum number of documents to return.
            offset (int): The starting point for retrieval.

        Returns:
            list: A list of matching documents (dicts).
        """
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")

        query = (
            "SELECT data FROM documents "
            "WHERE json_extract(data, '$.' || ?) = ? "
            "LIMIT ? OFFSET ?"
        )
        with self._lock:
            cursor = self._connection.execute(query, (key, value, limit, offset))
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def search_pattern(self, key, pattern, limit=100, offset=0):
        """
        Search documents matching a regex pattern.

        Args:
            key (str): The document field to match on.
            pattern (str): The regex pattern to match.
            limit (int): The maximum number of documents to return.
            offset (int): The starting point for retrieval.

        Returns:
            list: A list of matching documents (dicts).

        Raises:
            ValueError: If the key or pattern is invalid.
        """
        if not key or not isinstance(key, str):
            raise ValueError("key must be a non-empty string")
        if not pattern or not isinstance(pattern, str):
            raise ValueError("pattern must be a non-empty string")

        query = """
            SELECT data FROM documents
            WHERE json_extract(data, '$.' || ?) REGEXP ?
            LIMIT ? OFFSET ?
        """
        with self._lock:
            cursor = self._connection.execute(query, (key, pattern, limit, offset))
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def find_any(self, key, value_list):
        """
        Return documents where key matches any value in value_list.

        Args:
            key (str): The document field to match on.
            value_list (list): A list of possible values.

        Returns:
            list: A list of matching documents.
        """
        placeholders = ", ".join(["?"] * len(value_list))
        query = f"""
            SELECT DISTINCT documents.data
            FROM documents, json_each(documents.data, '$.' || ?)
            WHERE json_each.value IN ({placeholders})
        """
        with self._lock:
            cursor = self._connection.execute(query, [key] + value_list)
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def find_all(self, key, value_list):
        """
        Return documents where the key contains all values in value_list.

        Args:
            key (str): The field to match.
            value_list (list): The required values to match.

        Returns:
            list: A list of matching documents.
        """
        placeholders = ", ".join(["?"] * len(value_list))
        query = f"""
            SELECT documents.data
            FROM documents
            WHERE (
                SELECT COUNT(DISTINCT value)
                FROM json_each(documents.data, '$.' || ?)
                WHERE value IN ({placeholders})
            ) = ?
        """
        with self._lock:
            cursor = self._connection.execute(
                query, [key] + value_list + [len(value_list)]
            )
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def execute_async(self, func, *args, **kwargs):
        """
        Execute a function asynchronously using a thread pool.

        Args:
            func (callable): The function to execute.
            *args: Arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            concurrent.futures.Future: A Future object representing
            the execution.
        """
        return self.executor.submit(func, *args, **kwargs)

    def close(self):
        """
        Shutdown the thread pool executor and close the database connection.
        """
        self.executor.shutdown()
        with self._lock:
            self._connection.close()

