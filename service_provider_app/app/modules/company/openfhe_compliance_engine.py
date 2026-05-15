# service_provider_app/app/modules/company/openfhe_compliance_engine.py
from ...core.openfhe_engine import (
    dump_ciphertext,
    load_ciphertext,
    load_crypto_context,
    load_eval_mult_keys,
)


class OpenFHEComplianceEngine:
    def evaluate(self, payload: dict) -> dict:
        metadata = payload["metadata"]

        cc = load_crypto_context(metadata["crypto_context"])
        load_eval_mult_keys(cc, metadata["eval_mult_keys"])

        current_lat = load_ciphertext(payload["encrypted_current_lat"])
        current_lon = load_ciphertext(payload["encrypted_current_lon"])

        home_lat = load_ciphertext(payload["encrypted_home_lat"])
        home_lon = load_ciphertext(payload["encrypted_home_lon"])
        home_radius = load_ciphertext(payload["encrypted_home_radius"])

        office_lat = load_ciphertext(payload["encrypted_office_lat"])
        office_lon = load_ciphertext(payload["encrypted_office_lon"])
        office_radius = load_ciphertext(payload["encrypted_office_radius"])

        country_north = load_ciphertext(payload["encrypted_country_north"])
        country_south = load_ciphertext(payload["encrypted_country_south"])
        country_east = load_ciphertext(payload["encrypted_country_east"])
        country_west = load_ciphertext(payload["encrypted_country_west"])

        encrypted_home_margin = self._distance_margin(
            cc=cc,
            current_lat=current_lat,
            current_lon=current_lon,
            target_lat=home_lat,
            target_lon=home_lon,
            radius=home_radius,
        )

        encrypted_office_margin = self._distance_margin(
            cc=cc,
            current_lat=current_lat,
            current_lon=current_lon,
            target_lat=office_lat,
            target_lon=office_lon,
            radius=office_radius,
        )

        encrypted_country_north_margin = cc.EvalSub(country_north, current_lat)
        encrypted_country_south_margin = cc.EvalSub(current_lat, country_south)
        encrypted_country_east_margin = cc.EvalSub(country_east, current_lon)
        encrypted_country_west_margin = cc.EvalSub(current_lon, country_west)

        return {
            "encrypted_home_margin": dump_ciphertext(encrypted_home_margin),
            "encrypted_office_margin": dump_ciphertext(encrypted_office_margin),
            "encrypted_country_north_margin": dump_ciphertext(
                encrypted_country_north_margin
            ),
            "encrypted_country_south_margin": dump_ciphertext(
                encrypted_country_south_margin
            ),
            "encrypted_country_east_margin": dump_ciphertext(
                encrypted_country_east_margin
            ),
            "encrypted_country_west_margin": dump_ciphertext(
                encrypted_country_west_margin
            ),
        }

    def _distance_margin(
        self,
        cc,
        current_lat,
        current_lon,
        target_lat,
        target_lon,
        radius,
    ):
        dlat = cc.EvalSub(current_lat, target_lat)
        dlon = cc.EvalSub(current_lon, target_lon)

        dlat_squared = cc.EvalMult(dlat, dlat)
        dlon_squared = cc.EvalMult(dlon, dlon)

        distance_squared = cc.EvalAdd(dlat_squared, dlon_squared)

        radius_squared = cc.EvalMult(radius, radius)

        return cc.EvalSub(distance_squared, radius_squared)