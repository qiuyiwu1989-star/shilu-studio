"""Single-event writing rules shared by domain and transports."""
import hashlib
import os
from pathlib import Path

def recap_context():
    skill=(Path(__file__).parent/'skills/single-event-recap/SKILL.md').read_text()
    context={'skill':skill,'version':hashlib.sha256(skill.encode()).hexdigest(),
        'workflow':['list_projects','get_project','create_recap','get_project','submit_recap','validate_recap','human workbench: adopt, save, review, export']}
    profile_path=os.environ.get('SHILU_RECAP_PROFILE_PATH')
    if profile_path:
        try:
            profile=Path(profile_path).read_text(encoding='utf-8')
            if not profile.strip():raise ValueError('empty')
        except (OSError,UnicodeError,ValueError):
            raise ValueError('RECAP_PROFILE_UNAVAILABLE: configured single-event profile cannot be read or is empty') from None
        context['profile']=profile
        context['profile_version']=hashlib.sha256(profile.encode()).hexdigest()
        context['skill']=skill+'\n\n## Configured single-event profile\n\n'+profile
        context['version']=hashlib.sha256(context['skill'].encode()).hexdigest()
    return context

