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

        # All margins are computed using EvalSub only (no EvalMult / no level reduction).
        # The bounding-box check replaces the squared-distance check, eliminating the
        # multiplicative depth that caused CKKS MultipartyDecryptFusion to exceed its
        # approximation error threshold.

        # --- Home bounding-box margins ---
        print("[Compliance] computing home bbox margins...", flush=True)
        enc_home_north_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_home_north"]),
            load_ciphertext(payload["encrypted_current_lat"]),
        )
        enc_home_south_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lat"]),
            load_ciphertext(payload["encrypted_home_south"]),
        )
        enc_home_east_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_home_east"]),
            load_ciphertext(payload["encrypted_current_lon"]),
        )
        enc_home_west_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lon"]),
            load_ciphertext(payload["encrypted_home_west"]),
        )

        # --- Office bounding-box margins ---
        print("[Compliance] computing office bbox margins...", flush=True)
        enc_office_north_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_office_north"]),
            load_ciphertext(payload["encrypted_current_lat"]),
        )
        enc_office_south_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lat"]),
            load_ciphertext(payload["encrypted_office_south"]),
        )
        enc_office_east_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_office_east"]),
            load_ciphertext(payload["encrypted_current_lon"]),
        )
        enc_office_west_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lon"]),
            load_ciphertext(payload["encrypted_office_west"]),
        )

        # --- Country bounding-box margins (unchanged logic) ---
        print("[Compliance] computing country margins...", flush=True)
        enc_country_north_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_country_north"]),
            load_ciphertext(payload["encrypted_current_lat"]),
        )
        enc_country_south_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lat"]),
            load_ciphertext(payload["encrypted_country_south"]),
        )
        enc_country_east_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_country_east"]),
            load_ciphertext(payload["encrypted_current_lon"]),
        )
        enc_country_west_margin = cc.EvalSub(
            load_ciphertext(payload["encrypted_current_lon"]),
            load_ciphertext(payload["encrypted_country_west"]),
        )

        print("[Compliance] serializing results...", flush=True)
        return {
            "encrypted_home_north_margin":   dump_ciphertext(enc_home_north_margin),
            "encrypted_home_south_margin":   dump_ciphertext(enc_home_south_margin),
            "encrypted_home_east_margin":    dump_ciphertext(enc_home_east_margin),
            "encrypted_home_west_margin":    dump_ciphertext(enc_home_west_margin),
            "encrypted_office_north_margin": dump_ciphertext(enc_office_north_margin),
            "encrypted_office_south_margin": dump_ciphertext(enc_office_south_margin),
            "encrypted_office_east_margin":  dump_ciphertext(enc_office_east_margin),
            "encrypted_office_west_margin":  dump_ciphertext(enc_office_west_margin),
            "encrypted_country_north_margin": dump_ciphertext(enc_country_north_margin),
            "encrypted_country_south_margin": dump_ciphertext(enc_country_south_margin),
            "encrypted_country_east_margin":  dump_ciphertext(enc_country_east_margin),
            "encrypted_country_west_margin":  dump_ciphertext(enc_country_west_margin),
        }
