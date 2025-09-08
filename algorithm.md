Here's the stop loss addition for the PMCC strategy:

**Additional Parameters:**
```
// --- STOP LOSS PARAMETERS ---
SET leaps_stop_loss_percentage = 20.0   // Stop loss at 20% of LEAPS value
SET leaps_stop_loss_absolute = 500.0    // Absolute dollar stop loss for LEAPS
SET total_position_stop_loss = 1000.0   // Total position stop loss (LEAPS + short call)
SET trailing_stop_enabled = TRUE        // Enable trailing stop for LEAPS
SET trailing_stop_percentage = 15.0     // Trail by 15% from highest value
SET leaps_high_water_mark = 0.0         // Track highest LEAPS value for trailing

// --- STOP LOSS STATE TRACKING ---
DEFINE leaps_original_cost = 0.0
DEFINE position_opened_date = NULL
DEFINE stop_loss_triggered = FALSE
```

**Enhanced Initial Setup:**
```
PROCEDURE Initial_Setup():
    // Step 1: Buy the LEAPS call
    potential_leaps = FIND_OPTIONS(
        ticker=underlying_ticker, 
        type="CALL", 
        min_delta=leaps_delta_target, 
        min_dte=leaps_min_dte
    )
    
    long_leaps_call = SELECT_BEST_LEAPS(potential_leaps)
    
    IF long_leaps_call IS NULL:
        LOG("ERROR: No suitable LEAPS found. Abort setup.")
        RETURN FALSE
    END IF
    
    EXECUTE_BUY(long_leaps_call)
    
    // Initialize stop loss tracking
    SET leaps_original_cost = long_leaps_call.price
    SET leaps_high_water_mark = long_leaps_call.price
    SET position_opened_date = GET_CURRENT_DATE()
    SET stop_loss_triggered = FALSE
    
    LOG("Bought LEAPS: " + long_leaps_call.details + " for $" + long_leaps_call.price)
    LOG("Stop loss set at: " + CALCULATE_STOP_LOSS_LEVEL() + "%")

    // Step 2: Sell the first short call
    Sell_New_Short_Call()
    
    RETURN TRUE
END PROCEDURE
```

**Enhanced Daily Management with Stop Loss:**
```
PROCEDURE Daily_Management_Routine():
    // PRIORITY 1: Check LEAPS stop loss FIRST
    IF Check_LEAPS_Stop_Loss():
        // Stop loss triggered - liquidate entire position
        RETURN
    END IF
    
    // PRIORITY 2: Update trailing stop if enabled
    IF trailing_stop_enabled:
        Update_Trailing_Stop()
    END IF
    
    // PRIORITY 3: Normal short call management
    current_short_call = GET_POSITION(short_call)

    IF current_short_call IS NULL:
        Sell_New_Short_Call()
        RETURN
    END IF

    // Check short call P&L and delta as before
    current_loss = current_short_call.current_price - short_call_original_premium
    current_profit = short_call_original_premium - current_short_call.current_price
    loss_percentage = (current_loss / short_call_original_premium) * 100
    profit_percentage = (current_profit / short_call_original_premium) * 100
    
    // Short call stop loss (unchanged)
    IF current_loss >= max_loss_threshold OR loss_percentage >= max_loss_percentage:
        LOG("SHORT CALL LOSS LIMIT: $" + current_loss + " (" + loss_percentage + "%)")
        EXECUTE_BUY_TO_CLOSE(current_short_call)
        SET short_call = NULL
        SET short_call_original_premium = 0.0
        RETURN
    END IF
    
    // Profit taking (unchanged)
    IF profit_percentage >= profit_take_percentage:
        LOG("PROFIT TARGET HIT: " + profit_percentage + "% profit")
        EXECUTE_BUY_TO_CLOSE(current_short_call)
        SET short_call = NULL
        SET short_call_original_premium = 0.0
        RETURN
    END IF
    
    // Delta-based rolling (unchanged)
    current_delta = GET_CURRENT_DELTA(current_short_call)
    IF current_delta >= roll_trigger_delta:
        LOG("Delta trigger hit (" + current_delta + "). Rolling.")
        Roll_Short_Call(current_short_call)
    ELSE:
        LOG("Position stable. Delta: " + current_delta)
    END IF
END PROCEDURE
```

**Stop Loss Check Functions:**
```
FUNCTION Check_LEAPS_Stop_Loss():
    IF stop_loss_triggered:
        RETURN FALSE  // Already triggered
    END IF
    
    current_leaps = GET_POSITION(long_leaps_call)
    IF current_leaps IS NULL:
        RETURN FALSE  // No LEAPS position
    END IF
    
    current_leaps_value = current_leaps.current_price
    current_short_value = 0.0
    
    // Include short call value in total position calculation
    IF short_call IS NOT NULL:
        current_short_call = GET_POSITION(short_call)
        IF current_short_call IS NOT NULL:
            current_short_value = short_call_original_premium - current_short_call.current_price
        END IF
    END IF
    
    // Calculate losses
    leaps_loss = leaps_original_cost - current_leaps_value
    leaps_loss_percentage = (leaps_loss / leaps_original_cost) * 100
    total_position_value = current_leaps_value + current_short_value
    total_position_loss = leaps_original_cost - total_position_value
    
    // Check stop loss conditions
    stop_loss_hit = FALSE
    stop_reason = ""
    
    // Percentage-based stop loss
    IF leaps_loss_percentage >= leaps_stop_loss_percentage:
        stop_loss_hit = TRUE
        stop_reason = "LEAPS percentage stop loss: " + leaps_loss_percentage + "%"
    END IF
    
    // Absolute dollar stop loss for LEAPS
    IF leaps_loss >= leaps_stop_loss_absolute:
        stop_loss_hit = TRUE
        stop_reason = "LEAPS absolute stop loss: $" + leaps_loss
    END IF
    
    // Total position stop loss
    IF total_position_loss >= total_position_stop_loss:
        stop_loss_hit = TRUE
        stop_reason = "Total position stop loss: $" + total_position_loss
    END IF
    
    // Trailing stop loss
    IF trailing_stop_enabled:
        trailing_stop_level = leaps_high_water_mark * (1.0 - trailing_stop_percentage / 100.0)
        IF current_leaps_value <= trailing_stop_level:
            stop_loss_hit = TRUE
            stop_reason = "Trailing stop loss triggered at $" + current_leaps_value + " (trail from $" + leaps_high_water_mark + ")"
        END IF
    END IF
    
    IF stop_loss_hit:
        LOG("🛑 STOP LOSS TRIGGERED: " + stop_reason)
        LOG("LEAPS Loss: $" + leaps_loss + " (" + leaps_loss_percentage + "%)")
        LOG("Total Position Loss: $" + total_position_loss)
        
        // Liquidate entire position
        Liquidate_All_Positions()
        SET stop_loss_triggered = TRUE
        
        // Send emergency alert
        Send_Emergency_Alert("PMCC STOP LOSS TRIGGERED", stop_reason)
        
        RETURN TRUE
    END IF
    
    RETURN FALSE
END FUNCTION

PROCEDURE Update_Trailing_Stop():
    IF NOT trailing_stop_enabled:
        RETURN
    END IF
    
    current_leaps = GET_POSITION(long_leaps_call)
    IF current_leaps IS NULL:
        RETURN
    END IF
    
    current_value = current_leaps.current_price
    
    // Update high water mark if current value is higher
    IF current_value > leaps_high_water_mark:
        old_mark = leaps_high_water_mark
        SET leaps_high_water_mark = current_value
        
        new_trailing_stop = leaps_high_water_mark * (1.0 - trailing_stop_percentage / 100.0)
        LOG("📈 New high water mark: $" + leaps_high_water_mark + " (was $" + old_mark + ")")
        LOG("📉 Trailing stop now at: $" + new_trailing_stop)
    END IF
END PROCEDURE

PROCEDURE Liquidate_All_Positions():
    LOG("🚨 LIQUIDATING ALL POSITIONS 🚨")
    
    // Close short call first (if exists)
    IF short_call IS NOT NULL:
        current_short_call = GET_POSITION(short_call)
        IF current_short_call IS NOT NULL:
            EXECUTE_BUY_TO_CLOSE(current_short_call)
            LOG("Closed short call position")
        END IF
        SET short_call = NULL
        SET short_call_original_premium = 0.0
    END IF
    
    // Close LEAPS position
    IF long_leaps_call IS NOT NULL:
        current_leaps = GET_POSITION(long_leaps_call)
        IF current_leaps IS NOT NULL:
            EXECUTE_SELL_TO_CLOSE(current_leaps)
            LOG("Closed LEAPS position")
        END IF
        SET long_leaps_call = NULL
    END IF
    
    // Calculate final P&L
    Calculate_Final_PnL()
    
    LOG("🏁 All positions liquidated. Strategy stopped.")
END PROCEDURE

FUNCTION Calculate_Final_PnL():
    total_loss = leaps_original_cost
    
    // Subtract current LEAPS value if still have position
    IF long_leaps_call IS NOT NULL:
        current_leaps = GET_POSITION(long_leaps_call)
        IF current_leaps IS NOT NULL:
            total_loss -= current_leaps.current_price
        END IF
    END IF
    
    // Add short call profits collected over time
    // (This would need tracking throughout the strategy lifecycle)
    
    LOG("💰 Final P&L: -$" + total_loss)
    Send_Alert("PMCC Strategy Ended", "Final loss: $" + total_loss)
END FUNCTION

FUNCTION Send_Emergency_Alert(subject, message):
    // Implementation depends on your notification method
    // Email, SMS, Discord webhook, etc.
    LOG("🚨 EMERGENCY ALERT: " + subject + " - " + message)
    // send_email(subject, message)
    // send_sms(message)
END FUNCTION
```

**Additional Utility Functions:**
```
FUNCTION CALCULATE_STOP_LOSS_LEVEL():
    percentage_level = leaps_original_cost * (1.0 - leaps_stop_loss_percentage / 100.0)
    absolute_level = leaps_original_cost - leaps_stop_loss_absolute
    
    // Return the more conservative (higher) stop loss level
    RETURN MAX(percentage_level, absolute_level)
END FUNCTION

// Enhanced logging for stop loss monitoring
PROCEDURE Log_Position_Status():
    IF long_leaps_call IS NULL:
        RETURN
    END IF
    
    current_leaps = GET_POSITION(long_leaps_call)
    IF current_leaps IS NULL:
        RETURN
    END IF
    
    current_value = current_leaps.current_price
    unrealized_pnl = current_value - leaps_original_cost
    unrealized_percentage = (unrealized_pnl / leaps_original_cost) * 100
    
    stop_loss_level = CALCULATE_STOP_LOSS_LEVEL()
    distance_to_stop = ((current_value - stop_loss_level) / current_value) * 100
    
    LOG("📊 LEAPS Status: $" + current_value + " | P&L: $" + unrealized_pnl + " (" + unrealized_percentage + "%)")
    LOG("🛡️  Stop Loss: $" + stop_loss_level + " | Distance: " + distance_to_stop + "%")
    
    IF trailing_stop_enabled:
        trailing_level = leaps_high_water_mark * (1.0 - trailing_stop_percentage / 100.0)
        LOG("📈 Trailing Stop: $" + trailing_level + " | High: $" + leaps_high_water_mark)
    END IF
END PROCEDURE
```

**Usage Example:**
```
// Conservative settings for new traders
SET leaps_stop_loss_percentage = 15.0    // 15% max loss
SET leaps_stop_loss_absolute = 300.0     // $300 max loss
SET total_position_stop_loss = 500.0     // $500 total max loss
SET trailing_stop_enabled = TRUE
SET trailing_stop_percentage = 12.0      // 12% trailing stop

// Aggressive settings for experienced traders
SET leaps_stop_loss_percentage = 25.0    // 25% max loss
SET leaps_stop_loss_absolute = 1000.0    // $1000 max loss  
SET total_position_stop_loss = 1500.0    // $1500 total max loss
SET trailing_stop_enabled = FALSE        // No trailing stop
```

This adds comprehensive stop loss protection while maintaining the income-generating nature of the PMCC strategy. The trailing stop helps lock in profits during strong upward moves.
