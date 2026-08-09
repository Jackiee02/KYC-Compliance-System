from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz

from kyc_platform.domain.models import DuplicateCandidate, NormalizedCustomer


def _shingles(value: str) -> set[str]:
    compact = value.replace(" ", "")
    if len(compact) < 3:
        return {compact} if compact else {"<empty>"}
    return {compact[index : index + 3] for index in range(len(compact) - 2)}


class EntityResolutionService:
    """Find potential duplicates without deleting or merging source records."""

    def __init__(self, candidate_threshold: float = 0.78, lsh_threshold: float = 0.45, num_perm: int = 64) -> None:
        self.candidate_threshold = candidate_threshold
        self.lsh_threshold = lsh_threshold
        self.num_perm = num_perm

    def _minhash(self, value: str) -> MinHash:
        signature = MinHash(num_perm=self.num_perm)
        for token in sorted(_shingles(value)):
            signature.update(token.encode("utf-8"))
        return signature

    @staticmethod
    def _score(left: NormalizedCustomer, right: NormalizedCustomer) -> tuple[float, dict[str, float]]:
        name = fuzz.WRatio(left.normalized_name, right.normalized_name) / 100.0
        country = float(bool(left.registered_country and left.registered_country == right.registered_country))
        registration = float(
            bool(
                left.normalized_registration_number
                and right.normalized_registration_number
                and left.normalized_registration_number == right.normalized_registration_number
            )
        )
        score = min(1.0, 0.70 * name + 0.15 * country + 0.15 * registration)
        return score, {"name": name, "country": country, "registration_number": registration}

    def find_candidates(self, customers: list[NormalizedCustomer]) -> list[DuplicateCandidate]:
        lsh = MinHashLSH(threshold=self.lsh_threshold, num_perm=self.num_perm)
        signatures: dict[str, MinHash] = {}
        by_id = {customer.record_id: customer for customer in customers}
        for customer in customers:
            signature = self._minhash(customer.normalized_name)
            signatures[customer.record_id] = signature
            lsh.insert(customer.record_id, signature)

        seen: set[tuple[str, str]] = set()
        candidates: list[DuplicateCandidate] = []
        for customer in customers:
            nearby = lsh.query(signatures[customer.record_id])[:100]
            for other_id in nearby:
                if other_id == customer.record_id:
                    continue
                pair = tuple(sorted((customer.record_id, other_id)))
                if pair in seen:
                    continue
                seen.add(pair)
                score, components = self._score(customer, by_id[other_id])
                if score >= self.candidate_threshold:
                    candidates.append(
                        DuplicateCandidate(
                            left_record_id=pair[0],
                            right_record_id=pair[1],
                            score=round(score, 4),
                            components={key: round(value, 4) for key, value in components.items()},
                        )
                    )
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates
