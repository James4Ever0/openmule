import pathlib
import jinja2

crypto_wallet_address = "0x1234567890123456789012345678901234567890"
extra_info = f"""The crypto wallet address is Ethereum Mainnet. You may check the balance at https://etherscan.io/address/{crypto_wallet_address}."""

input_text = pathlib.Path("openmule-system-prompt.md").read_text(encoding="utf-8")

output_text = jinja2.Template(input_text).render(
    crypto_wallet_address=crypto_wallet_address,
    interval="1 hour",
    revenue_target="100 USD",
    extra_info=extra_info
)

print(output_text)

# TODO: render another prompt that only asks the agent to transfer money to the wallet address, but not killing the running instance based on a fixed time interval and assessment value. instead, we might kill instances which cannot compete with other instances. but that can be more complicated to implement. we can freeze those less competitive ones to be used later, only delete those without any finantial contribution.