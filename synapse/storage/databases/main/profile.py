# Copyright 2014-2016 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import TYPE_CHECKING, Optional

from synapse.api.errors import StoreError
from synapse.storage._base import SQLBaseStore
from synapse.storage.database import DatabasePool, LoggingDatabaseConnection
from synapse.storage.databases.main.roommember import ProfileInfo
from synapse.types import UserID

if TYPE_CHECKING:
    from synapse.server import HomeServer


class ProfileWorkerStore(SQLBaseStore):
    def __init__(
        self,
        database: DatabasePool,
        db_conn: LoggingDatabaseConnection,
        hs: "HomeServer",
    ):
        super().__init__(database, db_conn, hs)
        self.db_pool.updates.register_background_index_update(
            "profiles_full_user_id_key_idx",
            index_name="profiles_full_user_id_key",
            table="profiles",
            columns=["full_user_id"],
            unique=True,
        )

    async def get_profileinfo(self, user_localpart: str) -> ProfileInfo:
        try:
            profile = await self.db_pool.simple_select_one(
                table="profiles",
                keyvalues={"user_id": user_localpart},
                retcols=("displayname", "avatar_url"),
                desc="get_profileinfo",
            )
        except StoreError as e:
            if e.code == 404:
                # no match
                return ProfileInfo(None, None)
            else:
                raise

        return ProfileInfo(
            avatar_url=profile["avatar_url"], display_name=profile["displayname"]
        )

    async def get_profile_displayname(self, user_localpart: str) -> Optional[str]:
        return await self.db_pool.simple_select_one_onecol(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            retcol="displayname",
            desc="get_profile_displayname",
        )

    async def get_profile_avatar_url(self, user_localpart: str) -> Optional[str]:
        return await self.db_pool.simple_select_one_onecol(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            retcol="avatar_url",
            desc="get_profile_avatar_url",
        )

    async def create_profile(self, user_id: UserID) -> None:
        user_localpart = user_id.localpart
        await self.db_pool.simple_insert(
            table="profiles",
            values={"user_id": user_localpart, "full_user_id": user_id.to_string()},
            desc="create_profile",
        )

    async def set_profile_displayname(
        self, user_id: UserID, new_displayname: Optional[str]
    ) -> None:
        """
        Set the display name of a user.

        Args:
            user_id: The user's ID.
            new_displayname: The new display name. If this is None, the user's display
                name is removed.
        """
        user_localpart = user_id.localpart
        await self.db_pool.simple_upsert(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            values={
                "displayname": new_displayname,
                "full_user_id": user_id.to_string(),
            },
            desc="set_profile_displayname",
        )

    async def set_profile_avatar_url(
        self, user_id: UserID, new_avatar_url: Optional[str]
    ) -> None:
        """
        Set the avatar of a user.

        Args:
            user_id: The user's ID.
            new_avatar_url: The new avatar URL. If this is None, the user's avatar is
                removed.
        """
        user_localpart = user_id.localpart
        await self.db_pool.simple_upsert(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            values={"avatar_url": new_avatar_url, "full_user_id": user_id.to_string()},
            desc="set_profile_avatar_url",
        )


class ProfileStore(ProfileWorkerStore):
    pass
