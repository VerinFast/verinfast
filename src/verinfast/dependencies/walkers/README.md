# Walker F.A.Q.
## What's a Walker?
Walkers are functions that descend a file tree and find and parse manifests in a certain folder or subfolders.

## Neat. How many are there?
Ideally one for every manifest type.

## What's a manifest type? Is that a language?
No. Manifest types are files associated with build or software management packages. Think of the Gradle's build.gradle or Maven's pom.xml, as opposed to Java.

## Does a manifest need to have a central repository like Maven or PyPi?
No, although a `walker` may use a central repository to fetch supplementary data about a dependency listed in a manifest. For example, the npm walker installs all dependencies from the central repository, then reads the license string. This allows for capturing the whole dependency tree at once.

## What is the minimum a Walker must do?
A walker must update its internal list of `Entry` elements with at least a name and a source (e.g. `pandas` and `pip` respectively). Ideally an entry contains more, like a version, called a specifier, since it can be logical (e.g. `>=1.2.3`), a license, and a description.

## What about `requires` and `required_by`?
Those are reserved for future expansion and are not considered in scope today until more than ten manifest types are working.

## How can I contribute?
Write a walker. Test it locally. Get a copy of our contributor agreement on file, and then submit a PR. Preferably with unit tests.
