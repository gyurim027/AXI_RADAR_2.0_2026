"""I02 three-kind proposal submission. Existing GET /settings/versions is preserved."""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from app.core.auth import require_roles
from app.services.settings.proposals import SettingsProposalRepository, get_repository

router = APIRouter(prefix='/api/settings/proposals', tags=['산정 설정 제안 (I-02)'])
operator = require_roles('operator')


class ProposalBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra='forbid')
    policy_document: str = Field(alias='policyDocument', min_length=1, max_length=131072)
    expected_sha256: str = Field(alias='expectedSha256', pattern=r'^[0-9a-f]{64}$')


@router.post('/preflight')
def preflight(body: ProposalBody, user: dict = Depends(operator),
              repo: SettingsProposalRepository = Depends(get_repository)):
    return repo.preflight(body.policy_document, body.expected_sha256, user)


@router.post('')
def propose(body: ProposalBody, request: Request, response: Response,
            user: dict = Depends(operator), repo: SettingsProposalRepository = Depends(get_repository)):
    result = repo.propose(body.policy_document, body.expected_sha256, request, user)
    response.status_code = 200 if result['already_exists'] else 201
    return result
