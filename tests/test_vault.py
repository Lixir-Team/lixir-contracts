import brownie
import pytest
from hypothesis import strategies, settings
from brownie import chain, web3, reverts
from brownie.test import given, strategy
from lixir.strat_simp_gwap import getMainTicks
from lixir.positions import position_key

def test_vault_construction(vault, pool, registry, keeper, strategist, strat_simp_gwap):
    assert vault.token0() == pool.token0
    assert vault.token1() == pool.token1
    assert vault.strategy() == strat_simp_gwap
    assert vault.registry() == registry
    assert vault.keeper() == keeper
    assert vault.strategist() == strategist
    assert vault.activePool() == pool.pool
    assert vault.activeFee() == pool.fee
    data = strat_simp_gwap.vaultDatas(vault).dict()
    assert data["TICK_SHORT_DURATION"] == 60
    assert data["MAX_TICK_DIFF"] == 120
    assert data["mainSpread"] == 1800
    assert data["rangeSpread"] == 900
    assert data["tickCumulative"] > 0
    assert data["timestamp"] > 0
    main = vault.mainPosition().dict()
    range = vault.rangePosition().dict()
    tick = pool.pool.slot0().dict()["tick"]
    mainTicks = getMainTicks(tick, pool.pool.tickSpacing(), 1800)
    assert main["tickLower"] == mainTicks[0]
    assert main["tickUpper"] == mainTicks[1]
    assert range["tickLower"] == 0
    assert range["tickUpper"] == 0


@given(
    depositAmounts=strategies.lists(
        strategies.tuples(
            strategies.tuples(
                strategy("uint256", min_value=1e3, max_value=20e18),
                strategy("uint256", min_value=1e3, max_value=20e18),
            )
        ),
        min_size=4,
        max_size=4,
    )
)
@settings(max_examples=5)
def test_eth_vault_instant_out_lte_in(eth_vault, users, eth_pool, depositAmounts):
    depositors = users[:4]
    for i, u in enumerate(depositors):
        for dEth, d in depositAmounts[i]:
            # we test if a deposit and then immediate withdraw can profit
            shares = eth_vault.balanceOf(u)
            amountEthBefore = web3.eth.get_balance(u.address)
            amountBefore = eth_pool.token.balanceOf(u)
            eth_vault.depositETH(
                d, 0, 0, u, chain.time() + 60, {"from": u, "value": dEth}
            )
            sharesOut = eth_vault.balanceOf(u) - shares

            eth_vault.withdrawETH(sharesOut, 0, 0, u, chain.time() + 60, {"from": u})
            shares = eth_vault.balanceOf(u)
            amountEthAfter = web3.eth.get_balance(u.address)
            amountAfter = eth_pool.token.balanceOf(u)
            assert amountEthBefore >= amountEthAfter
            assert amountBefore >= amountAfter


@given(
    depositAmounts=strategies.lists(
        strategies.tuples(
            strategies.tuples(
                strategy("uint256", min_value=1e3, max_value=20e18),
                strategy("uint256", min_value=1e3, max_value=20e18),
            )
        ),
        min_size=4,
        max_size=4,
    )
)
@settings(max_examples=5)
def test_eth_vault_out_of_order_in_approx_out(
    eth_vault, users, eth_pool, depositAmounts
):
    depositors = users[:4]
    deposits = {u: [] for u in depositors}
    for i, u in enumerate(depositors):
        for dEth, d in depositAmounts[i]:
            shares = eth_vault.balanceOf(u)
            amountEthBefore = web3.eth.get_balance(u.address)
            amountBefore = eth_pool.token.balanceOf(u)
            # deposit to then withdraw in a different order
            eth_vault.depositETH(
                d, 0, 0, u, chain.time() + 60, {"from": u, "value": dEth}
            )
            sharesOut = eth_vault.balanceOf(u) - shares
            amountEthIn = amountEthBefore - web3.eth.get_balance(u.address)
            amountIn = amountBefore - eth_pool.token.balanceOf(u)
            deposits[u].append((sharesOut, amountEthIn, amountIn))
    for u in depositors:
        for d in deposits[u]:
            shares, amountEthIn, amountIn = d
            amountEthBefore = web3.eth.get_balance(u.address)
            amountBefore = eth_pool.token.balanceOf(u)
            eth_vault.withdrawETH(shares, 0, 0, u, chain.time() + 60, {"from": u})
            amountEthOut = web3.eth.get_balance(u.address) - amountEthBefore
            amountOut = eth_pool.token.balanceOf(u) - amountBefore
            # We don't check if out is less than in here, but we make that check above
            # so it doesn't happen in back-to-back deposit then withdraw
            # If someone sandwhiches a deposit and squeezes out a wei or two... gg hope you're proud of yourself
            assert int(amountEthOut) == pytest.approx(amountEthIn, abs=1e3)
            assert int(amountOut) == pytest.approx(amountIn, abs=1e3)


def test_eth_vault_withdraw_from(eth_vault, users, eth_pool):
    aEthBefore = web3.eth.get_balance(users[1])
    aInBefore = eth_pool.token.balanceOf(users[1])
    sharesBefore = eth_vault.balanceOf(users[1])
    eth_vault.depositETH(
        1e18, 0, 0, users[0], chain.time() + 60, {"from": users[0], "value": 1e18}
    )
    eth_vault.depositETH(
        1e18, 0, 0, users[1], chain.time() + 60, {"from": users[1], "value": 1e18}
    )
    aEthIn = aEthBefore - web3.eth.get_balance(users[1])
    aIn = aInBefore - eth_pool.token.balanceOf(users[1])
    shares = eth_vault.balanceOf(users[1]) - sharesBefore
    beforeEthBal, beforeBal = (
        web3.eth.get_balance(users[2].address),
        eth_pool.token.balanceOf(users[2].address),
    )
    eth_vault.approve(users[2], shares, {"from": users[1]})
    eth_vault.withdrawETHFrom(
        users[1], shares, 0, 0, users[2], chain.time() + 60, {"from": users[2]}
    )
    afterEthBal, afterBal = (
        web3.eth.get_balance(users[2].address),
        eth_pool.token.balanceOf(users[2].address),
    )
    assert int(beforeEthBal + aEthIn) == pytest.approx(afterEthBal)
    assert int(beforeBal + aIn) == pytest.approx(afterBal)
    with reverts("ALLOWANCE"):
        eth_vault.withdrawETHFrom(
            users[0], shares, 0, 0, users[2], chain.time() + 60, {"from": users[2]}
        )


@given(
    depositAmounts=strategies.lists(
        strategies.tuples(
            strategies.tuples(
                strategy("uint256", min_value=1e3, max_value=20e18),
                strategy("uint256", min_value=1e3, max_value=20e18),
            )
        ),
        min_size=4,
        max_size=4,
    )
)
@settings(max_examples=5)
def test_vault_instant_out_lte_in(vault, users, pool, depositAmounts):
    depositors = users[:4]
    for i, u in enumerate(depositors):
        for d0, d1 in depositAmounts[i]:
            # we test if a deposit and then immediate withdraw can profit
            shares = vault.balanceOf(u)
            amount0Before = pool.token0.balanceOf(u)
            amount1Before = pool.token1.balanceOf(u)
            vault.deposit(d0, d1, 0, 0, u, chain.time() + 60, {"from": u})
            sharesOut = vault.balanceOf(u) - shares

            vault.withdraw(sharesOut, 0, 0, u, chain.time() + 60, {"from": u})
            shares = vault.balanceOf(u)
            amount0After = pool.token0.balanceOf(u)
            amount1After = pool.token1.balanceOf(u)
            assert amount0Before >= amount0After
            assert amount1Before >= amount1After


@given(
    depositAmounts=strategies.lists(
        strategies.tuples(
            strategies.tuples(
                strategy("uint256", min_value=1e3, max_value=20e18),
                strategy("uint256", min_value=1e3, max_value=20e18),
            )
        ),
        min_size=4,
        max_size=4,
    )
)
@settings(max_examples=5)
def test_vault_out_of_order_in_approx_out(vault, users, pool, depositAmounts):
    depositors = users[:4]
    deposits = {u: [] for u in depositors}
    for i, u in enumerate(depositors):
        for d0, d1 in depositAmounts[i]:
            shares = vault.balanceOf(u)
            amount0Before = pool.token0.balanceOf(u)
            amount1Before = pool.token1.balanceOf(u)
            # deposit to then withdraw in a different order
            vault.deposit(d0, d1, 0, 0, u, chain.time() + 60, {"from": u})
            sharesOut = vault.balanceOf(u) - shares
            amount0In = amount0Before - pool.token0.balanceOf(u)
            amount1In = amount1Before - pool.token1.balanceOf(u)
            deposits[u].append((sharesOut, amount0In, amount1In))
    for u in depositors:
        for d in deposits[u]:
            shares, amount0In, amount1In = d
            amount0Before = pool.token0.balanceOf(u)
            amount1Before = pool.token1.balanceOf(u)
            vault.withdraw(shares, 0, 0, u, chain.time() + 60, {"from": u})
            amount0Out = pool.token0.balanceOf(u) - amount0Before
            amount1Out = pool.token1.balanceOf(u) - amount1Before
            # We don't check if out is less than in here, but we make that check above
            # so it doesn't happen in back-to-back deposit then withdraw
            # If someone sandwhiches a deposit and squeezes out a wei or two... gg hope you're proud of yourself
            assert int(amount0Out) == pytest.approx(amount0In, abs=1e3)
            assert int(amount1Out) == pytest.approx(amount1In, abs=1e3)


def test_eth_vault_withdraw_from(vault, users, pool):
    a0InBefore = pool.token0.balanceOf(users[1])
    a1InBefore = pool.token1.balanceOf(users[1])
    sharesBefore = vault.balanceOf(users[1])
    vault.deposit(1e18, 1e18, 0, 0, users[0], chain.time() + 60, {"from": users[0]})
    vault.deposit(1e18, 1e18, 0, 0, users[1], chain.time() + 60, {"from": users[1]})
    a0In = pool.token0.balanceOf(users[1]) - a0InBefore
    a1In = pool.token1.balanceOf(users[1]) - a1InBefore
    shares = vault.balanceOf(users[1]) - sharesBefore
    before0Bal, beforeBal = (
        pool.token0.balanceOf(users[2].address),
        pool.token1.balanceOf(users[2].address),
    )
    vault.approve(users[2], shares, {"from": users[1]})
    vault.withdrawFrom(
        users[1], shares, 0, 0, users[2], chain.time() + 60, {"from": users[2]}
    )
    after0Bal, afterBal = (
        pool.token0.balanceOf(users[2].address),
        pool.token1.balanceOf(users[2].address),
    )
    assert int(before0Bal + a0In) == pytest.approx(after0Bal)
    assert int(beforeBal + a1In) == pytest.approx(afterBal)
    with reverts("ALLOWANCE"):
        vault.withdrawFrom(
            users[0], shares, 0, 0, users[2], chain.time() + 60, {"from": users[2]}
        )


def test_perf_fee(
    vault,
    strategist,
    pool,
    user,
    strat_simp_gwap,
    keeper,
    mock_router,
    delegate,
    registry,
):
    registry.setFeeTo(delegate, {"from": delegate})
    strat_simp_gwap.setMaxTickDiff(vault, 2 ** 23 - 2, {"from": strategist})
    perfFee = (1 / 3)
    vault.setPerformanceFee(perfFee * registry.PERFORMANCE_FEE_PRECISION(), {"from": strategist})
    chain.sleep(300)
    strat_simp_gwap.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
    vault.deposit(
        1e30,
        1e30,
        0,
        0,
        user,
        chain.time() + 60,
        {"from": user},
    )
    lower, upper = vault.mainPosition()
    startSqrtRatioX96 = pool.pool.slot0().dict()['sqrtPriceX96']
    lower = int(1.0001 ** (lower / 2) * (1 << 96))
    upper = int(1.0001 ** (upper / 2) * (1 << 96))
    assert vault.balanceOf(delegate) == 0
    t0b, t1b, _, _ = vault.calculateTotals()
    for _ in range(5):
        mock_router.swapLimit(pool.pool, True, 1e20, lower, {"from": user})
        mock_router.swapLimit(pool.pool, False, 1e20, upper, {"from": user})
    mock_router.swapLimit(pool.pool, False, 1e20, startSqrtRatioX96, {"from": user})
    price = (startSqrtRatioX96 / (1 << 96)) ** 2
    strat_simp_gwap.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
    t0a, t1a, _, _ = vault.calculateTotals()
    totalBefore = t0b * price + t1b
    totalAfter = t0a * price + t1a
    posGrowth = 1 - (totalBefore / totalAfter)
    feeGrowth = vault.balanceOf(delegate) / vault.totalSupply()
    assert vault.balanceOf(delegate) > 0
    assert (feeGrowth / posGrowth) == pytest.approx(perfFee, rel=1e-3)


# def test_emergency_exit(
#     vault, pauser, pool, users, strat_simp_gwap, keeper, delegate, registry
# ):
#     registry.setFeeTo(delegate, {"from": delegate})
#     strat_simp_gwap.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
#     balancesBefore = [
#         (pool.token0.balanceOf(u), pool.token1.balanceOf(u)) for u in users
#     ]
#     for u in users:
#         vault.deposit(
#             1e30,
#             1e30,
#             0,
#             0,
#             u,
#             chain.time() + 60,
#             {"from": u},
#         )
#     vault.emergencyExit({"from": pauser})
#     with brownie.reverts("Pausable: paused"):
#         vault.emergencyExit({"from": pauser})
#     _, _, mL, rL = vault.calculateTotals()
#     assert mL == 0
#     assert rL == 0
#     for u in users:
#         with brownie.reverts("Pausable: paused"):
#             vault.deposit(
#                 1e30,
#                 1e30,
#                 0,
#                 0,
#                 u,
#                 chain.time() + 60,
#                 {"from": u},
#             )
#     for u in users:
#         vault.withdraw(vault.balanceOf(u), 0, 0, u, chain.time() + 60, {"from": u})
#     balancesAfter = [
#         (pool.token0.balanceOf(u), pool.token1.balanceOf(u)) for u in users
#     ]
#     for before, after in zip(balancesBefore, balancesAfter):
#         assert int(after[0]) == pytest.approx(before[0])
#         assert int(after[1]) == pytest.approx(before[1])
#     total0, total1, mL, rL = vault.calculateTotals()
#     assert total0 <= len(users)
#     assert total1 <= len(users)
#     assert mL == 0
#     assert rL == 0


def test_change_strategy(
    vault,
    pool,
    users,
    strat_simp_gwap,
    strategist,
    keeper,
    delegate,
    registry,
    LixirStrategySimpleGWAP,
):
    chain.sleep(3000)
    strat_simp_gwap.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
    for u in users:
        vault.deposit(
            1e30,
            1e30,
            0,
            0,
            u,
            chain.time() + 60,
            {"from": u},
        )
    chain.sleep(3000)
    strat_simp_gwap.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
    vaultData = strat_simp_gwap.vaultDatas(vault).dict()
    new_strat = LixirStrategySimpleGWAP.deploy(registry, {"from": delegate})
    registry.grantRole(registry.strategy_role(), new_strat)
    vault.setStrategy(new_strat, {"from": strategist})
    new_strat.configureVault(
        vault,
        vault.activeFee(),
        vaultData["TICK_SHORT_DURATION"],
        vaultData["MAX_TICK_DIFF"],
        vaultData["mainSpread"],
        vaultData["rangeSpread"],
        {"from": strategist},
    )
    chain.sleep(3000)
    with brownie.reverts(""):
        strat_simp_gwap.rebalance(
            vault, pool.pool.slot0().dict()["tick"], {"from": keeper}
        )
    new_strat.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})
    for u in users:
        vault.withdraw(vault.balanceOf(u) / 2, 0, 0, u, chain.time() + 60, {"from": u})
    for u in users:
        vault.deposit(
                    1e18,
                    1e18,
                    0,
                    0,
                    u,
                    chain.time() + 60,
                    {"from": u},
                )
    chain.sleep(3000)
    new_strat.rebalance(vault, pool.pool.slot0().dict()["tick"], {"from": keeper})

def test_out_of_range(vault, mock_router, pool, users, keeper, strat_simp_gwap):
    vault.deposit(1e18, 1e18, 0, 0, users[0], chain.time() + 60, {"from": users[0]})
    pool = pool.pool
    mock_router.swap(pool, True, 1e8, {"from": users[0]})
    strat_simp_gwap.rebalance(
            vault, pool.slot0().dict()["tick"], {"from": keeper}
        )
    mainData = vault.mainPosition().dict()
    rangeData = vault.rangePosition().dict()
    main = pool.positions(position_key(vault.address, mainData['tickLower'], mainData['tickUpper'])).dict()
    range = pool.positions(position_key(vault.address, mainData['tickLower'], mainData['tickUpper'])).dict()
    assert main['_liquidity'] > 0
    assert range['_liquidity'] > 0
    below0, below1, _, _ = vault.calculateTotalsFromTick(min(mainData['tickLower'], rangeData['tickLower']) - 1)
    above0, above1, _, _ = vault.calculateTotalsFromTick(max(mainData['tickUpper'], rangeData['tickUpper']) + 1)
    assert min(below0, below1) == 0
    assert min(above0, above1) == 0


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
