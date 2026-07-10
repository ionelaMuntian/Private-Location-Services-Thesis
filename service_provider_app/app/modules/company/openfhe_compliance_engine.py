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
