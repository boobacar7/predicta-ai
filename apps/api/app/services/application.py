from datetime import date

from app.core.clock import Clock, to_rfc3339
from app.core.config import Settings
from app.repositories.protocols import RepositoryBundle
from app.schemas import (
    AnalystMessage,
    AnalystSession,
    DashboardSnapshot,
    Fact,
    FactPack,
    MatchStatus,
    PerformanceReport,
    Pick,
    SportCode,
    ValueOpportunity,
)
from app.services.catalog import MatchService
from app.services.projections import to_match_summary
from app.services.value_service import opportunities_for_match


class DashboardService:
    def __init__(self, repos: RepositoryBundle, clock: Clock) -> None:
        self._repos = repos
        self._clock = clock

    def snapshot(self) -> DashboardSnapshot:
        today = to_rfc3339(self._clock.now())[:10]
        matches = [
            to_match_summary(match)
            for match in self._repos.matches.list_matches(sport=None, league_id=None, match_date=None, status=None)
            if to_rfc3339(match.kickoff_at)[:10] == today
        ]
        values: list[ValueOpportunity] = []
        for match in self._repos.matches.list_matches(sport=None, league_id=None, match_date=None, status=None):
            best = max(
                opportunities_for_match(match),
                key=lambda item: item.edge_raw or -1,
                default=None,
            )
            if best is not None:
                values.append(best)
        values.sort(key=lambda item: item.edge_raw or -1, reverse=True)
        return DashboardSnapshot(
            headline=f"Journée mock du {today}",
            sports=self._repos.catalog.list_sports(),
            matches_today=matches,
            picks=self._repos.signals.list_picks(),
            value_opportunities=values[:8],
            insights=self._repos.signals.list_insights(),
            model_health=self._repos.signals.get_performance().summary,
        )


class PickService:
    def __init__(self, repos: RepositoryBundle) -> None:
        self._repos = repos

    def list_picks(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[Pick]:
        items: list[Pick] = []
        for pick in self._repos.signals.list_picks():
            match = pick.match
            if sport and match.sport != sport:
                continue
            if league_id and match.league.id != league_id:
                continue
            if status and match.status != status:
                continue
            if match_date and to_rfc3339(match.kickoff_at)[:10] != match_date.isoformat():
                continue
            items.append(pick)
        return items


class ValueListService:
    def __init__(self, repos: RepositoryBundle) -> None:
        self._repos = repos

    def list_values(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[ValueOpportunity]:
        items: list[ValueOpportunity] = []
        matches = self._repos.matches.list_matches(
            sport=sport, league_id=league_id, match_date=match_date, status=status
        )
        for match in matches:
            items.extend(opportunities_for_match(match))
        items.sort(key=lambda item: item.edge_raw or -1, reverse=True)
        return items


class PerformanceService:
    def __init__(self, repos: RepositoryBundle) -> None:
        self._repos = repos

    def report(self) -> PerformanceReport:
        return self._repos.signals.get_performance()


class AnalystService:
    def __init__(self, matches: MatchService, clock: Clock, settings: Settings) -> None:
        self._matches = matches
        self._clock = clock
        self._settings = settings

    def analyze(self, match_id: str, question: str | None) -> AnalystSession:
        match = self._matches.get_match(match_id)
        fact_pack = self._build_fact_pack(match)
        available = [fact for fact in fact_pack.facts if fact.availability == "available"]
        missing = [fact for fact in fact_pack.facts if fact.availability == "unavailable"]
        cited = [fact.id for fact in available[:4]]
        leading = None
        if match.prediction:
            leading = max(
                match.prediction.outcomes,
                key=lambda item: item.calibrated_probability if item.calibrated_probability is not None else -1,
            )
        if match.prediction and leading is not None:
            probability = (
                "indisponible" if leading.calibrated_probability is None else f"{leading.calibrated_probability:.0%}"
            )
            body = (
                f"À partir du fact pack {fact_pack.id}, le modèle {match.prediction.model_version} "
                f"attribue la plus haute probabilité calibrée à {leading.label} ({probability}). "
                "Cette valeur est une estimation statistique, pas un résultat futur. "
            )
        else:
            body = (
                "Aucune prédiction n'est présente dans le fact pack. L'analyste ne peut pas inventer de probabilités. "
            )
        if missing:
            body += (
                "Champs explicitement indisponibles : "
                + ", ".join(item.label for item in missing)
                + ". Ils n'ont pas été complétés."
            )
        else:
            body += "Aucun champ manquant n'est signalé dans ce paquet."

        messages: list[AnalystMessage] = []
        if question:
            messages.append(
                AnalystMessage(
                    id=f"msg_user_{match_id}",
                    role="user",
                    body=question,
                    cited_fact_ids=[],
                    created_at=self._clock.shift(minutes=-1),
                )
            )
        messages.append(
            AnalystMessage(
                id=f"msg_analyst_{match_id}",
                role="analyst",
                body=body.strip(),
                cited_fact_ids=cited,
                created_at=self._clock.now(),
            )
        )
        return AnalystSession(
            match_id=match_id,
            fact_pack=fact_pack,
            messages=messages,
            llm_model=self._settings.analyst_llm_model,
            prompt_version=self._settings.analyst_prompt_version,
            disclaimer=(
                "Réponse construite uniquement à partir du fact pack validé. Aucune donnée absente n'a été extrapolée."
            ),
        )

    def _build_fact_pack(self, match) -> FactPack:
        now = self._clock.now()
        facts: list[Fact] = [
            Fact(
                id=f"{match.id}_kickoff",
                label="Coup d'envoi",
                value=to_rfc3339(match.kickoff_at),
                unit="timestamp",
                source="mock.fixtures.v1" if self._settings.repository == "mock" else "predicta.matches",
                observed_at=now,
                availability="available",
            ),
            Fact(
                id=f"{match.id}_status",
                label="Statut",
                value=match.status,
                unit=None,
                source="mock.fixtures.v1" if self._settings.repository == "mock" else "predicta.matches",
                observed_at=now,
                availability="available",
            ),
        ]
        if match.prediction:
            for outcome in match.prediction.outcomes:
                facts.append(
                    Fact(
                        id=f"{match.id}_p_{outcome.selection}",
                        label=f"Probabilité calibrée · {outcome.label}",
                        value=(
                            "unavailable"
                            if outcome.calibrated_probability is None
                            else str(outcome.calibrated_probability)
                        ),
                        unit="probability",
                        source=match.prediction.model_version,
                        observed_at=match.prediction.cutoff_at,
                        availability=("unavailable" if outcome.calibrated_probability is None else "available"),
                    )
                )
            facts.append(
                Fact(
                    id=f"{match.id}_model",
                    label="Version de modèle",
                    value=match.prediction.model_version,
                    unit=None,
                    source="mock.registry" if self._settings.repository == "mock" else "predicta.models",
                    observed_at=match.prediction.cutoff_at,
                    availability="available",
                )
            )
        for field in match.unavailable_fields:
            facts.append(
                Fact(
                    id=f"{match.id}_missing_{field.field}",
                    label=field.field,
                    value="unavailable",
                    unit=None,
                    source="mock.fixtures.v1" if self._settings.repository == "mock" else "predicta.quality",
                    observed_at=now,
                    availability="unavailable",
                )
            )
        return FactPack(
            id=f"fp_{match.id}",
            match_id=match.id,
            generated_at=now,
            facts=facts,
        )
