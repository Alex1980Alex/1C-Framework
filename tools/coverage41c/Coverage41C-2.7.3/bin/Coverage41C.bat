@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem

@if "%DEBUG%" == "" @echo off
@rem ##########################################################################
@rem
@rem  Coverage41C startup script for Windows
@rem
@rem ##########################################################################

SetLocal EnableExtensions EnableDelayedExpansion

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%" == "" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and COVERAGE41_C_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS=

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if "%ERRORLEVEL%" == "0" goto init

echo.
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto init

echo.
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:init
@rem Get command-line arguments, handling Windows variants

if not "%OS%" == "Windows_NT" goto win9xME_args

:win9xME_args
@rem Slurp the command line arguments.
set CMD_LINE_ARGS=
set _SKIP=2

:win9xME_args_slurp
if "x%~1" == "x" goto execute

set CMD_LINE_ARGS=%*

:execute
@rem Setup the command line

if "%EDT_LOCATION%" == "" (
    set EDT_LOCATION=""
    FOR /F "tokens=*" %%G IN ('ring edt locations list') DO IF EXIST "%%G\plugins\com._1c.g5.v8.dt.debug*.jar" (set EDT_LOCATION=%%G\plugins)
)

set EDT_CLASSPATH=
for /f "tokens=*" %%F in ('dir /b /a:-d "%EDT_LOCATION%\com._1c.g5.v8.dt.debug.core_*.jar"') do call set EDT_CLASSPATH=!EDT_CLASSPATH!;%EDT_LOCATION%\%%F
for /f "tokens=*" %%F in ('dir /b /a:-d "%EDT_LOCATION%\com._1c.g5.v8.dt.debug.model_*.jar"') do call set EDT_CLASSPATH=!EDT_CLASSPATH!;%EDT_LOCATION%\%%F

set CLASSPATH=%APP_HOME%\lib\Coverage41C-2.7.3.jar;%APP_HOME%\lib\picocli-4.6.3.jar;%APP_HOME%\lib\slf4j-simple-2.0.3.jar;%APP_HOME%\lib\jetty-client-11.0.12.jar;%APP_HOME%\lib\mdclasses-0.10.3.jar;%APP_HOME%\lib\jetty-http-11.0.12.jar;%APP_HOME%\lib\jetty-alpn-client-11.0.12.jar;%APP_HOME%\lib\jetty-io-11.0.12.jar;%APP_HOME%\lib\supportconf-0.1.1.jar;%APP_HOME%\lib\jetty-util-11.0.12.jar;%APP_HOME%\lib\asciitable-0.3.2.jar;%APP_HOME%\lib\ascii-utf-themes-0.0.1.jar;%APP_HOME%\lib\char-translation-0.0.2.jar;%APP_HOME%\lib\skb-interfaces-0.0.1.jar;%APP_HOME%\lib\bsl-common-library-904b9172.jar;%APP_HOME%\lib\slf4j-api-2.0.3.jar;%APP_HOME%\lib\ipcsocket-1.5.0.jar;%APP_HOME%\lib\org.eclipse.emf.ecore.xcore.lib-1.6.0.jar;%APP_HOME%\lib\org.eclipse.emf.ecore.xmi-2.16.0.jar;%APP_HOME%\lib\org.eclipse.emf.ecore-2.38.0.jar;%APP_HOME%\lib\org.eclipse.emf.common-2.40.0.jar;%APP_HOME%\lib\org.eclipse.core.runtime-3.24.100.jar;%APP_HOME%\lib\org.eclipse.core.jobs-3.15.400.jar;%APP_HOME%\lib\org.eclipse.core.contenttype-3.9.600.jar;%APP_HOME%\lib\org.eclipse.equinox.preferences-3.11.200.jar;%APP_HOME%\lib\org.eclipse.equinox.app-1.7.200.jar;%APP_HOME%\lib\org.eclipse.equinox.registry-3.12.200.jar;%APP_HOME%\lib\org.eclipse.equinox.common-3.19.200.jar;%APP_HOME%\lib\org.eclipse.osgi-3.22.0.jar;%APP_HOME%\lib\org.eclipse.osgi.services-3.10.200.jar;%APP_HOME%\lib\guice-5.1.0.jar;%APP_HOME%\lib\org.eclipse.xtext.xbase.lib-2.37.0.jar;%APP_HOME%\lib\guava-33.3.1-jre.jar;%APP_HOME%\lib\bsl-parser-0.21.0.jar;%APP_HOME%\lib\jna-platform-5.12.0.jar;%APP_HOME%\lib\jna-5.12.0.jar;%APP_HOME%\lib\failureaccess-1.0.2.jar;%APP_HOME%\lib\listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar;%APP_HOME%\lib\jsr305-3.0.2.jar;%APP_HOME%\lib\checker-qual-3.43.0.jar;%APP_HOME%\lib\error_prone_annotations-2.28.0.jar;%APP_HOME%\lib\j2objc-annotations-3.0.0.jar;%APP_HOME%\lib\javax.inject-1.jar;%APP_HOME%\lib\aopalliance-1.0.jar;%APP_HOME%\lib\commons-collections4-4.4.jar;%APP_HOME%\lib\utils-0.4.0.jar;%APP_HOME%\lib\vavr-0.10.2.jar;%APP_HOME%\lib\xstream-1.4.19.jar;%APP_HOME%\lib\commons-io-2.8.0.jar;%APP_HOME%\lib\commons-lang3-3.11.jar;%APP_HOME%\lib\classgraph-4.8.147.jar;%APP_HOME%\lib\antlr4-4.9.0.jar;%APP_HOME%\lib\commons-beanutils-1.9.4.jar;%APP_HOME%\lib\org.osgi.service.prefs-1.1.2.jar;%APP_HOME%\lib\vavr-match-0.10.2.jar;%APP_HOME%\lib\mxparser-1.2.2.jar;%APP_HOME%\lib\antlr4-runtime-4.9.0.jar;%APP_HOME%\lib\commons-logging-1.2.jar;%APP_HOME%\lib\commons-collections-3.2.2.jar;%APP_HOME%\lib\osgi.annotation-8.0.1.jar;%APP_HOME%\lib\ST4-4.0.8.jar;%APP_HOME%\lib\antlr4-4.5.1.jar;%APP_HOME%\lib\xmlpull-1.1.3.1.jar;%APP_HOME%\lib\antlr-runtime-3.5.2.jar%EDT_CLASSPATH%

@rem Execute Coverage41C
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %COVERAGE41_C_OPTS%  -classpath "%CLASSPATH%" com.clouds42.Coverage41C %CMD_LINE_ARGS%

:end
@rem End local scope for the variables with windows NT shell
if "%ERRORLEVEL%"=="0" goto mainEnd

:fail
rem Set variable COVERAGE41_C_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
if  not "" == "%COVERAGE41_C_EXIT_CONSOLE%" exit 1
exit /b 1

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega
