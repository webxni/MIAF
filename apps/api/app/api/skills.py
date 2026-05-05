from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DB, RequestCtx
from app.schemas.skill import SkillManifestOut, SkillRunLogOut, SkillRunRequest, SkillToggleRequest
from app.services.audit import write_audit
from app.services.skills import list_skill_manifests, list_skill_runs, run_skill, set_skill_enabled

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=list[SkillManifestOut])
async def list_skills_endpoint(db: DB, me: CurrentUserDep) -> list[SkillManifestOut]:
    return [SkillManifestOut.model_validate(item) for item in await list_skill_manifests(db, tenant_id=me.tenant_id)]


@router.post("/{skill_name}/state", response_model=SkillManifestOut)
async def set_skill_state_endpoint(
    skill_name: str,
    payload: SkillToggleRequest,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> SkillManifestOut:
    await set_skill_enabled(db, tenant_id=me.tenant_id, skill_name=skill_name, enabled=payload.enabled)
    manifest = next(item for item in await list_skill_manifests(db, tenant_id=me.tenant_id) if item["name"] == skill_name)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="update",
        object_type="skill_state",
        object_id=skill_name,
        after={"enabled": payload.enabled},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return SkillManifestOut.model_validate(manifest)


@router.post("/{skill_name}/run", response_model=SkillRunLogOut)
async def run_skill_endpoint(
    skill_name: str,
    payload: SkillRunRequest,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> SkillRunLogOut:
    row = await run_skill(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=payload.entity_id,
        skill_name=skill_name,
        input_payload=payload.input,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=payload.entity_id,
        action="run",
        object_type="skill",
        object_id=skill_name,
        after={"result_status": row.result_status, "permissions": row.permissions},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return SkillRunLogOut.model_validate(row)


@router.get("/runs", response_model=list[SkillRunLogOut])
async def list_skill_runs_endpoint(
    db: DB,
    me: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[SkillRunLogOut]:
    return [SkillRunLogOut.model_validate(item) for item in await list_skill_runs(db, tenant_id=me.tenant_id, limit=limit)]
