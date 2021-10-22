from typing import Tuple, Union

# import brownie
from brownie.network.account import Account
from brownie import chain, web3
from brownie.test import strategy, given
from hypothesis import settings
from collections import namedtuple
from random import randrange
import random
from lixir.strat_simp_gwap import getMainTicks
import pytest
from decimal import Decimal, getcontext

getcontext().prec = 100

MAX_EXAMPLES = 200
STATEFUL_STEP_COUNT = 30


class UserDiff:
    def __init__(
        self,
        shares,
        totalValueBefore,
        userValueBefore,
        totalSupplyBefore,
        block_number,
        txindex,
    ):
        self.shares = shares
        self.totalValueBefore = totalValueBefore
        self.userValueBefore = userValueBefore
        self.totalSupplyBefore = totalSupplyBefore
        self.block_number = block_number
        self.txindex = txindex

    def __lt__(self, otherDiff):
        if self.block_number == otherDiff.block_number:
            return self.txindex < otherDiff.txindex
        else:
            return self.block_number < otherDiff.block_number


Swap = namedtuple(
    "Swap",
    ["amountOut", "zeroForOne", "rebalanceIndex", "priceBefore", "tickBefore", "priceAfter", "tickAfter"],
)


class StateMachine:
    amount0Desired = strategy("uint256", min_value=1e12, max_value=1e30)
    amount1Desired = strategy("uint256", min_value=1e12, max_value=1e30)

    # amount0Desired = strategy("uint256", min_value=5e5, max_value=1e30)
    # amount1Desired = strategy("uint256", min_value=5e5, max_value=1e30)
    swapAmountIn = strategy("uint256", min_value=1e3, max_value=1e30)
    zeroForOne = strategy("bool")
    time = strategy("uint256", max_value=60 * 60 * 24 * 30)
    randseed=strategy("uint256", min_value=1e12, max_value=1e30)
    def __init__(
        self, user, vault, pool, strategist, strat_simp_gwap, keeper, mock_router
    ):
        self.vault = vault
        self.pool = pool.pool
        self.token0 = pool.token0
        self.token1 = pool.token1
        self.mock_router = mock_router
        self.user = user
        self.deposits: list[UserDiff] = []
        self.strategist = strategist
        self.strat_simp_gwap = strat_simp_gwap
        self.keeper = keeper
        self.strat_simp_gwap.setMaxTickDiff(
            self.vault, 2 ** 23 - 2, {"from": self.strategist}
        )
        self.swaps = []
        self.tickSpacing = self.pool.tickSpacing()
        self.startPrice = 0
        self.lastWithdraw = None
        self.rebalanceIndex = 0

    # reset all stateful values
    def initialize(self):
        self.deposits = []
        self.swaps = []
        self.startPrice = (self.pool.slot0().dict()["sqrtPriceX96"] / (1 << 96)) ** 2
        self.lastWithdraw: Union[None, Tuple[Account, UserDiff]] = None

    # rebalance by keeper
    def rule_rebalance(self):
        chain.sleep(100)
        try:
            self.strat_simp_gwap.rebalance(
                self.vault, self.pool.slot0().dict()["tick"], {"from": self.keeper}
            )
        except:
            total0, total1, _, _ = self.vault.calculateTotals()
            assert total0 < 1e5 or total1 < 1e5
        self.rebalanceIndex += 1

    # deposit one of the users
    def rule_deposit(self, amount0Desired, amount1Desired):
        try:
            user = self.user
            shares = self.vault.balanceOf(user)
            userValueBefore = self._calcUserValue(user)
            total0, total1, _, _ = self.vault.calculateTotals()
            totalValueBefore = total0 * self.startPrice + total1
            totalSupplyBefore = self.vault.totalSupply()
            tx = self.vault.deposit(
                amount0Desired,
                amount1Desired,
                0,
                0,
                user,
                chain.time() + 60,
                {"from": user},
            )
            shares = self.vault.balanceOf(user) - shares
            assert shares >= 0
            self.deposits.append(
                UserDiff(
                    shares,
                    totalValueBefore,
                    userValueBefore,
                    totalSupplyBefore,
                    tx.block_number,
                    tx.txindex,
                )
            )
        except:
            return

    # withdraw a random deposit entry
    def rule_withdraw(self, randseed):
        random.seed(randseed)
        user = self.user
        depositsLength = len(self.deposits)
        if depositsLength == 0:
            return
        deposit = self.deposits.pop(randrange(depositsLength))
        self.vault.withdraw(
            deposit.shares, 0, 0, user, chain.time() + 60, {"from": user}
        )
        if len(self.deposits) > 0:
            self.lastWithdraw = deposit
        else:
            self.startPrice = (self.pool.slot0().dict()["sqrtPriceX96"] / (1 << 96)) ** 2
            self.lastWithdraw = None

    # swaps some amount
    def rule_swap(self, swapAmountIn, zeroForOne):
        if swapAmountIn <= 0:
            return
        slot0Before = self.pool.slot0().dict()
        priceBefore = slot0Before["sqrtPriceX96"]
        tickBefore = slot0Before["tick"]
        if zeroForOne:
            amountOut = self.token1.balanceOf(self.user)
            limit = tickBefore - 900
        else:
            amountOut = self.token0.balanceOf(self.user)
            limit = tickBefore + 900
        limit = int(1.0001 ** (limit / 2) * (1 << 96))
        self.mock_router.swapLimit(
            self.pool, zeroForOne, swapAmountIn, limit, {"from": self.user}
        )
        if zeroForOne:
            amountOut = self.token1.balanceOf(self.user) - amountOut
        else:
            amountOut = self.token0.balanceOf(self.user) - amountOut
        slot0After = self.pool.slot0().dict()
        priceAfter = slot0After["sqrtPriceX96"]
        tickAfter = slot0After["tick"]
        self.swaps.append(
            Swap(amountOut, zeroForOne, self.rebalanceIndex, priceBefore, tickBefore, priceAfter, tickAfter)
        )

    # fast forward in time
    def rule_fast_forward(self, time):
        chain.sleep(time)

    # swap back to previous price
    def rule_swap_back(self):
        if len(self.swaps) == 0:
            return
        swap = self.swaps.pop()
        if (self.rebalanceIndex - swap.rebalanceIndex) <= 1:
            try:
                self.mock_router.swapLimit(
                    self.pool,
                    not swap.zeroForOne,
                    self.token1.balanceOf(self.user)
                    if swap.zeroForOne
                    else self.token0.balanceOf(self.user),
                    swap.priceBefore,
                    {"from": self.user},
                )
            except:
                pass
        else:
            self.swaps = []

    def invariant(self):
        if self.lastWithdraw == None:
            return
        diff = self.lastWithdraw
        self.lastWithdraw = None
        totalSupply = self.vault.totalSupply()
        total0, total1, _, _ = self.vault.calculateTotals()
        valAfter = int(Decimal(total0) * Decimal(self.startPrice) + Decimal(total1))
        total_loss = 0
        badDeposits = []
        for d in [d for d in self.deposits if d < diff and d.totalSupplyBefore > 0]:
            valBeforeAdjusted = int(Decimal(d.totalValueBefore) * Decimal(totalSupply) / Decimal(d.totalSupplyBefore))
            if valAfter < valBeforeAdjusted and int(valAfter) != pytest.approx(
                valBeforeAdjusted, rel=5e-2
            ):
                total_loss = max(valBeforeAdjusted - valAfter, total_loss)
                badDeposits.append(valBeforeAdjusted)
        assert total_loss <= 1000

    def _calcUserValue(self, user):
        return self.token0.balanceOf(user) * self.startPrice + self.token1.balanceOf(
            user
        )

def test_stateful(
    state_machine, vault, pool, strategist, strat_simp_gwap, keeper, mock_router, user
):
    state_machine(
        StateMachine,
        user,
        vault,
        pool,
        strategist,
        strat_simp_gwap,
        keeper,
        mock_router,
        settings={
            "max_examples": MAX_EXAMPLES,
            "stateful_step_count": STATEFUL_STEP_COUNT,
        },
    )
