from scripts.bootstrap import do_bootstrap
from eth_abi import registry
from scripts.helpers.vault_helpers import config_to_args
from lixir.system import (
    LixirAccounts,
    deploy_dependencies,
    LixirSystem,
    get_accounts,
)
from scripts.deploy_test_pools import deploy_pools
from brownie import TestERC20, BootstrapDeposits, web3


def test_bootstrap(uni_gov, accounts):
    weth, uni_factory = deploy_dependencies(uni_gov)
    start_lixir_accounts = LixirAccounts(
        accounts[0], accounts[0], accounts[0], accounts[0], accounts[0], accounts[0]
    )
    system = LixirSystem.deploy(weth, uni_factory, start_lixir_accounts)
    gov_role = system.registry.gov_role()
    delegate_role = system.registry.delegate_role()
    strategist_role = system.registry.strategist_role()
    fee_setter_role = system.registry.fee_setter_role()
    pauser_role = system.registry.pauser_role()
    keeper_role = system.registry.keeper_role()
    deployer_role = system.registry.deployer_role()
    factory_role = system.registry.factory_role()
    vault_implementation_role = system.registry.vault_implementation_role()
    eth_vault_implementation_role = system.registry.eth_vault_implementation_role()
    strategy_role = system.registry.strategy_role()
    roles = [
        gov_role,
        delegate_role,
        strategist_role,
        fee_setter_role,
        pauser_role,
        keeper_role,
        deployer_role,
        factory_role,
        vault_implementation_role,
        eth_vault_implementation_role,
        strategy_role,
    ]
    for r in roles:
        assert system.registry.getRoleMemberCount(r) == 1
    bootstrap = BootstrapDeposits.deploy({"from": accounts[0]})
    system.registry.grantRole(strategist_role, bootstrap)
    assert system.registry.getRoleMemberCount(strategist_role) == 2
    vault_configs = [config_to_args(c) for c in deploy_pools(uni_factory, weth)]
    vaults = []
    for vault_config in vault_configs:
        if vault_config.tokenA == system.weth or vault_config.tokenB == system.weth:
            vault = system.deploy_eth_vault(vault_config, bootstrap)
        else:
            vault = system.deploy_vault(vault_config, bootstrap)
        vaults.append(vault)
    for vault in vaults:
        TestERC20.at(vault.token0()).mint(bootstrap, 1e20, {"from": accounts[0]})
        TestERC20.at(vault.token1()).mint(bootstrap, 1e20, {"from": accounts[0]})
    accounts[0].transfer(bootstrap, "100 ether")
    tokens = [[v.token0(), v.token1()] for v in vaults]
    tokens = list(set(TestERC20.at(v) for w in tokens for v in w if v != system.weth))
    do_bootstrap(system, bootstrap)
    balancesBefore = [web3.eth.get_balance(accounts[0].address)] + [
        t.balanceOf(accounts[0]) for t in tokens
    ]
    bootstrap.withdraw(tokens)
    balancesAfter = [web3.eth.get_balance(accounts[0].address)] + [
        t.balanceOf(accounts[0]) for t in tokens
    ]
    assert web3.eth.get_balance(bootstrap.address) == 0
    for before, after in zip(balancesBefore, balancesAfter):
        assert before <= after
    for t in tokens:
        assert t.balanceOf(bootstrap) == 0
    for v in vaults:
        assert v.totalSupply() > 0
        assert v.MAX_SUPPLY() == 0
        assert TestERC20.at(v.token0()).balanceOf(v.activePool()) > 0
        assert TestERC20.at(v.token1()).balanceOf(v.activePool()) > 0
        assert v.balanceOf(bootstrap) == 0
        assert v.balanceOf(accounts[0]) > 0
