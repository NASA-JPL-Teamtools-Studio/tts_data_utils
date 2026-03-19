# Lorem Ipsum Data Generation

Data Utilities now includes a powerful feature for generating realistic dummy data for any DataContainer type. This is useful for prototyping, testing, and documentation purposes.

## Basic Usage

To generate lorem ipsum data for any DataContainer, simply pass an integer to the `lorem` parameter when creating the container:

```python
from data_utils.multimission.evr import EvrContainer

# Create an EVR container with 10 dummy records
evr_container = EvrContainer(lorem=10)

# Print the container to see the generated data
print(evr_container)
```

## How It Works

The lorem ipsum generator analyzes the `DICT_VALID_KEYS` of the container's `DATA_ITEM_CLS` to understand the expected structure and data types. It then generates appropriate random values for each field, taking into account:

- Field names (e.g., fields containing "id", "name", "message", etc.)
- Data types (strings, integers, floats, datetimes, etc.)
- Allowed null values

## Smart Value Generation

The generator tries to create meaningful data based on field names:

- ID fields get numeric or formatted ID values
- Name fields get short lorem ipsum phrases
- Message fields get longer lorem ipsum text
- Status fields get values like "pending", "completed", etc.
- Time fields get random datetimes within the last year
- Boolean fields get random True/False values

## Example

```python
from data_utils.multimission.evr import EvrContainer
from data_utils.multimission.eha import EhaContainer
from data_utils.core.generic import GenericContainer

# Create containers with different numbers of records
evr_container = EvrContainer(lorem=5)
eha_container = EhaContainer(lorem=3)
generic_container = GenericContainer(lorem=4, name="My Lorem Data")

# Use them like any other container
print(f"EVR Container has {len(evr_container)} records")
print(f"First EVR message: {evr_container[0].message}")

# You can also convert to other formats
html_table = evr_container.power_table()
```

## Use Cases

- **Prototyping**: Quickly create realistic data structures without writing boilerplate
- **Testing**: Generate test data with predictable structure but random values
- **Documentation**: Create examples with realistic data
- **UI Development**: Populate interfaces with dummy data during development

## Customization

The lorem ipsum generator is designed to work with any DataContainer subclass, including custom ones you create. As long as your class follows the DataContainer pattern with a properly defined DATA_ITEM_CLS and DICT_VALID_KEYS, the generator will produce appropriate data.

For more examples, see the demo script at `data_utils/demo/lorem_demo.py`.
