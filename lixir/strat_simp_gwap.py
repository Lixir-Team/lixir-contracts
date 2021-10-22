minTick = -887272
maxTick = -minTick

def roundTickDown(tick, tickSpacing):
    tickMod = tick % tickSpacing
    return max(tick if tickMod == 0 else tick - tickMod, minTick)

def roundTickUp(tick, tickSpacing):
    tickDown = roundTickDown(tick, tickSpacing)
    return min(tick if tick == tickDown else tickDown + tickSpacing, maxTick)

def getMainTicks(tick_gwap, tickSpacing, spread):
    lower = roundTickDown(tick_gwap - spread, tickSpacing)
    upper = roundTickUp(tick_gwap + spread, tickSpacing)
    assert lower < upper
    return (lower, upper)