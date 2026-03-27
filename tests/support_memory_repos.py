# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.crons.models import JobsFile
from copaw.app.crons.repo.base import BaseJobRepository


class InMemoryJobRepository(BaseJobRepository):
    def __init__(self) -> None:
        self._jobs_file = JobsFile(version=1, jobs=[])

    async def load(self) -> JobsFile:
        return self._jobs_file.model_copy(deep=True)

    async def save(self, jobs_file: JobsFile) -> None:
        self._jobs_file = jobs_file.model_copy(deep=True)
