# Action examples

Author: OSAZEE.

Examples are illustrative; replace the example entity IDs with your own selections in the action editor. They are not installed automatically.

## Toggle two lights

In **Button 1 - Triple click**, add **Light: Toggle** and select both lights. A subsequent successful gesture toggles them back.

## Double-click cover control with stop while moving

In **Button 1 - Double click**, add an **If-then** action:

- If your cover is **opening OR closing**, call **Cover: Stop**.
- Otherwise, call **Cover: Open**.

Use the same moving condition for **Button 2 - Double click**, with **Cover: Close** in its otherwise branch. The cover integration must expose moving states and support the stop action.

## Combined actions

Use **Both buttons - Short press** to toggle one plug and **Both buttons - Hold** to toggle another. Do not duplicate those assignments in the single-button action lists or another automation listening to the same remote.

## Daily brightness preference

A 06:00 brightness preference is a separate scheduled automation, not a remote gesture. Do not assume `light.turn_on` can set an off light's brightness without powering it on. Whether a truly non-powering brightness update is possible depends on the light/integration. Do not simulate it by briefly turning the light on and off.

## More than one action

Use **Add action** repeatedly within a gesture. Actions run in order. Avoid long delays: the blueprint ignores further gestures while its current run is active.
