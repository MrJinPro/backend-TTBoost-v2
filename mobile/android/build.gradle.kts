// Compatibility bridge for plugins that still expect old Groovy-style
// rootProject.ext.flutter.compileSdkVersion/minSdkVersion/targetSdkVersion.
extra["flutter"] = mapOf(
    "compileSdkVersion" to 35,
    "minSdkVersion" to 21,
    "targetSdkVersion" to 35,
)

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
