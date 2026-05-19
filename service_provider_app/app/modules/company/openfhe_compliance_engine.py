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

        print("[Compliance] deserializing crypto context...", flush=True)
        cc = load_crypto_context(metadata["crypto_context"])
        print("[Compliance] loading eval mult keys...", flush=True)
        load_eval_mult_keys(cc, metadata["eval_mult_keys"])
        # Fresh deserialization for every ciphertext use avoids any in-place
        # level-reduction that OpenFHE's C++ Python bindings may perform on
        # shared ciphertext objects across consecutive EvalMult/EvalSub calls.
        print("[Compliance] computing home margin...", flush=True)
        encrypted_home_margin = self._distance_margin(
            cc=cc,
            current_lat=load_ciphertext(payload["encrypted_current_lat"]),
            current_lon=load_ciphertext(payload["encrypted_current_lon"]),
            target_lat=load_ciphertext(payload["encrypted_home_lat"]),
            target_lon=load_ciphertext(payload["encrypted_home_lon"]),
            radius=load_ciphertext(payload["encrypted_home_radius"]),
        )

        print("[Compliance] computing office margin...", flush=True)
        encrypted_office_margin = self._distance_margin(
            cc=cc,
            current_lat=load_ciphertext(payload["encrypted_current_lat"]),
            current_lon=load_ciphertext(payload["encrypted_current_lon"]),
            target_lat=load_ciphertext(payload["encrypted_office_lat"]),
            target_lon=load_ciphertext(payload["encrypted_office_lon"]),
            radius=load_ciphertext(payload["encrypted_office_radius"]),
        )

        print("[Compliance] computing country margins...", flush=True)
        encrypted_country_north_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_country_north"]),
            load_ciphertext(payload["encrypted_current_lat"]),
        )
        encrypted_country_south_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lat"]),
            load_ciphertext(payload["encrypted_country_south"]),
        )
        encrypted_country_east_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_country_east"]),
            load_ciphertext(payload["encrypted_current_lon"]),
        )
        encrypted_country_west_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lon"]),
            load_ciphertext(payload["encrypted_country_west"]),
        )

        print("[Compliance] serializing results...", flush=True)
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
        print("[Compliance]   EvalSub lat...", flush=True)
        dlat = cc.EvalSub(current_lat, target_lat)
        print("[Compliance]   EvalSub lon...", flush=True)
        dlon = cc.EvalSub(current_lon, target_lon)

        print("[Compliance]   EvalMult dlat²...", flush=True)
        dlat_squared = cc.EvalMult(dlat, dlat)
        print("[Compliance]   EvalMult dlon²...", flush=True)
        dlon_squared = cc.EvalMult(dlon, dlon)

        print("[Compliance]   EvalAdd dist²...", flush=True)
        distance_squared = cc.EvalAdd(dlat_squared, dlon_squared)

        print("[Compliance]   EvalMult radius²...", flush=True)
        radius_squared = cc.EvalMult(radius, radius)

        print("[Compliance]   EvalSub margin...", flush=True)
        return cc.EvalSub(distance_squared, radius_squared)